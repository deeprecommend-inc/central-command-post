from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import re
import ipaddress
import asyncio
import aiohttp

from ..models.database import (
    get_db,
    ProxyIP,
    ProxyTestResult,
    ProxyTypeEnum,
    ProxyQualityEnum,
    PlatformEnum
)

router = APIRouter(prefix="/proxy-ips")


# Pydantic Models
class ProxyIPCreate(BaseModel):
    ip_address: str
    port: int = Field(ge=1, le=65535)
    proxy_type: ProxyTypeEnum = ProxyTypeEnum.HTTP
    username: Optional[str] = None
    password: Optional[str] = None
    is_residential: bool = False
    is_mobile: bool = False
    country_code: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    isp: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None


class ProxyIPBulkImport(BaseModel):
    """一括インポート用（複数形式をサポート）"""
    raw_text: str  # IP:PORT or IP:PORT:USER:PASS など
    proxy_type: ProxyTypeEnum = ProxyTypeEnum.HTTP
    is_residential: bool = False
    source: Optional[str] = None


class ProxyIPUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_banned: Optional[bool] = None
    notes: Optional[str] = None


class ProxyIPResponse(BaseModel):
    id: int
    ip_address: str
    port: int
    proxy_type: str
    is_residential: bool
    is_mobile: bool
    country_code: Optional[str]
    quality: str
    response_time_ms: Optional[float]
    success_rate: float
    total_requests: int
    last_used_at: Optional[datetime]
    last_tested_at: Optional[datetime]
    is_active: bool
    is_banned: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ProxyTestRequest(BaseModel):
    proxy_ids: Optional[List[int]] = None  # 指定されたプロキシのみテスト
    test_all: bool = False  # 全てのアクティブなプロキシをテスト
    platform: Optional[PlatformEnum] = None  # プラットフォーム固有のテスト


class ProxyFilterRequest(BaseModel):
    quality_levels: Optional[List[ProxyQualityEnum]] = None
    is_residential: Optional[bool] = None
    is_active: Optional[bool] = True
    country_codes: Optional[List[str]] = None
    min_success_rate: Optional[float] = None


# Utility Functions
def extract_ips_from_text(text: str) -> List[dict]:
    """
    テキストから複数のプロキシ情報を抽出
    サポート形式:
    - IP:PORT
    - IP:PORT:USER:PASS
    - USER:PASS@IP:PORT
    - http://IP:PORT
    - socks5://IP:PORT
    """
    results = []

    # 各行を処理
    lines = text.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        proxy_info = parse_proxy_line(line)
        if proxy_info:
            results.append(proxy_info)

    return results


def parse_proxy_line(line: str) -> Optional[dict]:
    """1行のプロキシ情報をパース"""

    # プロトコル指定あり: http://IP:PORT, socks5://IP:PORT
    protocol_match = re.match(r'^(https?|socks5)://(.+)', line)
    if protocol_match:
        protocol = protocol_match.group(1)
        rest = protocol_match.group(2)
        proxy_type = ProxyTypeEnum.SOCKS5 if protocol == "socks5" else ProxyTypeEnum.HTTP
    else:
        rest = line
        proxy_type = ProxyTypeEnum.HTTP

    # USER:PASS@IP:PORT 形式
    auth_match = re.match(r'^([^:]+):([^@]+)@([^:]+):(\d+)', rest)
    if auth_match:
        return {
            'ip_address': auth_match.group(3),
            'port': int(auth_match.group(4)),
            'username': auth_match.group(1),
            'password': auth_match.group(2),
            'proxy_type': proxy_type
        }

    # IP:PORT:USER:PASS 形式
    full_match = re.match(r'^([^:]+):(\d+):([^:]+):(.+)', rest)
    if full_match:
        return {
            'ip_address': full_match.group(1),
            'port': int(full_match.group(2)),
            'username': full_match.group(3),
            'password': full_match.group(4),
            'proxy_type': proxy_type
        }

    # IP:PORT 形式
    simple_match = re.match(r'^([^:]+):(\d+)', rest)
    if simple_match:
        return {
            'ip_address': simple_match.group(1),
            'port': int(simple_match.group(2)),
            'proxy_type': proxy_type
        }

    return None


def validate_ip(ip_str: str) -> bool:
    """IPアドレスの妥当性をチェック"""
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False


async def test_proxy(proxy: ProxyIP, test_url: str = "http://httpbin.org/ip") -> dict:
    """
    プロキシをテストして品質を評価
    """
    proxy_url = f"{proxy.proxy_type.value}://"
    if proxy.username and proxy.password_encrypted:
        # TODO: パスワードの復号化
        proxy_url += f"{proxy.username}:DECRYPTED_PASSWORD@"
    proxy_url += f"{proxy.ip_address}:{proxy.port}"

    start_time = datetime.now()

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                test_url,
                proxy=proxy_url,
                ssl=False
            ) as response:
                response_time = (datetime.now() - start_time).total_seconds() * 1000

                if response.status == 200:
                    data = await response.json()

                    return {
                        'success': True,
                        'response_time_ms': response_time,
                        'status_code': response.status,
                        'detected_ip': data.get('origin', proxy.ip_address),
                        'error_message': None
                    }
                else:
                    return {
                        'success': False,
                        'response_time_ms': response_time,
                        'status_code': response.status,
                        'error_message': f"HTTP {response.status}"
                    }

    except asyncio.TimeoutError:
        return {
            'success': False,
            'response_time_ms': 10000,
            'error_message': "Timeout"
        }
    except Exception as e:
        return {
            'success': False,
            'response_time_ms': (datetime.now() - start_time).total_seconds() * 1000,
            'error_message': str(e)
        }


def calculate_quality(response_time_ms: float, success_rate: float) -> ProxyQualityEnum:
    """応答時間と成功率から品質を判定"""
    if response_time_ms < 500 and success_rate > 0.95:
        return ProxyQualityEnum.EXCELLENT
    elif response_time_ms < 1000 and success_rate > 0.85:
        return ProxyQualityEnum.GOOD
    elif response_time_ms < 2000 and success_rate > 0.70:
        return ProxyQualityEnum.FAIR
    else:
        return ProxyQualityEnum.POOR


# API Endpoints
@router.post("/", response_model=ProxyIPResponse)
async def create_proxy(
    proxy_data: ProxyIPCreate,
    db: AsyncSession = Depends(get_db)
):
    """プロキシを1件追加"""

    # IPアドレスの検証
    if not validate_ip(proxy_data.ip_address):
        raise HTTPException(status_code=400, detail="Invalid IP address")

    # 重複チェック
    result = await db.execute(
        select(ProxyIP).where(
            and_(
                ProxyIP.ip_address == proxy_data.ip_address,
                ProxyIP.port == proxy_data.port
            )
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Proxy already exists")

    # TODO: パスワードの暗号化
    password_encrypted = proxy_data.password if proxy_data.password else None

    proxy = ProxyIP(
        ip_address=proxy_data.ip_address,
        port=proxy_data.port,
        proxy_type=proxy_data.proxy_type,
        username=proxy_data.username,
        password_encrypted=password_encrypted,
        is_residential=proxy_data.is_residential,
        is_mobile=proxy_data.is_mobile,
        country_code=proxy_data.country_code,
        region=proxy_data.region,
        city=proxy_data.city,
        isp=proxy_data.isp,
        source=proxy_data.source,
        notes=proxy_data.notes
    )

    db.add(proxy)
    await db.commit()
    await db.refresh(proxy)

    return proxy


@router.post("/bulk-import")
async def bulk_import_proxies(
    import_data: ProxyIPBulkImport,
    db: AsyncSession = Depends(get_db)
):
    """複数のプロキシを一括インポート"""

    # テキストからプロキシ情報を抽出
    proxy_list = extract_ips_from_text(import_data.raw_text)

    if not proxy_list:
        raise HTTPException(status_code=400, detail="No valid proxies found in text")

    added_count = 0
    skipped_count = 0
    invalid_count = 0

    for proxy_info in proxy_list:
        # IPアドレスの検証
        if not validate_ip(proxy_info['ip_address']):
            invalid_count += 1
            continue

        # 重複チェック
        result = await db.execute(
            select(ProxyIP).where(
                and_(
                    ProxyIP.ip_address == proxy_info['ip_address'],
                    ProxyIP.port == proxy_info['port']
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            skipped_count += 1
            continue

        # プロキシを追加
        proxy = ProxyIP(
            ip_address=proxy_info['ip_address'],
            port=proxy_info['port'],
            proxy_type=proxy_info.get('proxy_type', import_data.proxy_type),
            username=proxy_info.get('username'),
            password_encrypted=proxy_info.get('password'),  # TODO: 暗号化
            is_residential=import_data.is_residential,
            source=import_data.source
        )
        db.add(proxy)
        added_count += 1

    await db.commit()

    return {
        "total_parsed": len(proxy_list),
        "added": added_count,
        "skipped_duplicates": skipped_count,
        "invalid": invalid_count
    }


@router.get("/", response_model=List[ProxyIPResponse])
async def list_proxies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    quality: Optional[ProxyQualityEnum] = None,
    is_active: Optional[bool] = None,
    is_residential: Optional[bool] = None,
    country_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """プロキシ一覧を取得"""

    query = select(ProxyIP)

    # フィルタリング
    filters = []
    if quality:
        filters.append(ProxyIP.quality == quality)
    if is_active is not None:
        filters.append(ProxyIP.is_active == is_active)
    if is_residential is not None:
        filters.append(ProxyIP.is_residential == is_residential)
    if country_code:
        filters.append(ProxyIP.country_code == country_code)

    if filters:
        query = query.where(and_(*filters))

    # ソート: 品質が良く、最近テストされたものを優先
    query = query.order_by(
        ProxyIP.quality.asc(),
        ProxyIP.last_tested_at.desc().nullslast()
    ).offset(skip).limit(limit)

    result = await db.execute(query)
    proxies = result.scalars().all()

    return proxies


@router.post("/filter", response_model=List[ProxyIPResponse])
async def filter_high_quality_proxies(
    filter_req: ProxyFilterRequest,
    db: AsyncSession = Depends(get_db)
):
    """高品質なプロキシのみをフィルタリング"""

    query = select(ProxyIP)

    filters = []

    # 品質フィルター
    if filter_req.quality_levels:
        filters.append(ProxyIP.quality.in_(filter_req.quality_levels))

    # アクティブフィルター
    if filter_req.is_active is not None:
        filters.append(ProxyIP.is_active == filter_req.is_active)

    # レジデンシャルフィルター
    if filter_req.is_residential is not None:
        filters.append(ProxyIP.is_residential == filter_req.is_residential)

    # 国フィルター
    if filter_req.country_codes:
        filters.append(ProxyIP.country_code.in_(filter_req.country_codes))

    # 成功率フィルター
    if filter_req.min_success_rate:
        filters.append(ProxyIP.success_rate >= filter_req.min_success_rate)

    # 禁止されていないもの
    filters.append(ProxyIP.is_banned == False)

    if filters:
        query = query.where(and_(*filters))

    # 高品質順にソート
    query = query.order_by(
        ProxyIP.quality.asc(),
        ProxyIP.success_rate.desc(),
        ProxyIP.response_time_ms.asc().nullslast()
    )

    result = await db.execute(query)
    proxies = result.scalars().all()

    return proxies


@router.post("/test")
async def test_proxies(
    test_req: ProxyTestRequest,
    db: AsyncSession = Depends(get_db)
):
    """プロキシをテストして品質を更新"""

    # テスト対象のプロキシを取得
    if test_req.proxy_ids:
        query = select(ProxyIP).where(ProxyIP.id.in_(test_req.proxy_ids))
    elif test_req.test_all:
        query = select(ProxyIP).where(
            and_(
                ProxyIP.is_active == True,
                ProxyIP.is_banned == False
            )
        )
    else:
        raise HTTPException(status_code=400, detail="Specify proxy_ids or set test_all=true")

    result = await db.execute(query)
    proxies = result.scalars().all()

    if not proxies:
        raise HTTPException(status_code=404, detail="No proxies found to test")

    # 各プロキシをテスト
    tested_count = 0
    for proxy in proxies:
        test_result = await test_proxy(proxy)

        # テスト結果を記録
        test_record = ProxyTestResult(
            proxy_id=proxy.id,
            success=test_result['success'],
            response_time_ms=test_result.get('response_time_ms'),
            status_code=test_result.get('status_code'),
            error_message=test_result.get('error_message'),
            detected_ip=test_result.get('detected_ip'),
            platform=test_req.platform
        )
        db.add(test_record)

        # プロキシの統計を更新
        proxy.total_requests += 1
        if test_result['success']:
            proxy.successful_requests += 1
        else:
            proxy.failed_requests += 1

        proxy.success_rate = proxy.successful_requests / proxy.total_requests if proxy.total_requests > 0 else 0.0

        # 応答時間の更新（移動平均）
        if test_result.get('response_time_ms'):
            if proxy.response_time_ms:
                proxy.response_time_ms = (proxy.response_time_ms * 0.7) + (test_result['response_time_ms'] * 0.3)
            else:
                proxy.response_time_ms = test_result['response_time_ms']

        # 品質の再評価
        proxy.quality = calculate_quality(
            proxy.response_time_ms or 9999,
            proxy.success_rate
        )

        proxy.last_tested_at = datetime.now()

        tested_count += 1

    await db.commit()

    return {
        "tested_count": tested_count,
        "message": f"Tested {tested_count} proxies"
    }


@router.patch("/{proxy_id}", response_model=ProxyIPResponse)
async def update_proxy(
    proxy_id: int,
    update_data: ProxyIPUpdate,
    db: AsyncSession = Depends(get_db)
):
    """プロキシ情報を更新"""

    result = await db.execute(
        select(ProxyIP).where(ProxyIP.id == proxy_id)
    )
    proxy = result.scalar_one_or_none()

    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")

    # 更新
    if update_data.is_active is not None:
        proxy.is_active = update_data.is_active
    if update_data.is_banned is not None:
        proxy.is_banned = update_data.is_banned
    if update_data.notes is not None:
        proxy.notes = update_data.notes

    await db.commit()
    await db.refresh(proxy)

    return proxy


@router.delete("/{proxy_id}")
async def delete_proxy(
    proxy_id: int,
    db: AsyncSession = Depends(get_db)
):
    """プロキシを削除"""

    result = await db.execute(
        select(ProxyIP).where(ProxyIP.id == proxy_id)
    )
    proxy = result.scalar_one_or_none()

    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")

    await db.delete(proxy)
    await db.commit()

    return {"message": "Proxy deleted"}


@router.get("/stats")
async def get_proxy_stats(db: AsyncSession = Depends(get_db)):
    """プロキシプールの統計情報"""

    # 総数
    total_result = await db.execute(select(func.count(ProxyIP.id)))
    total = total_result.scalar()

    # アクティブ数
    active_result = await db.execute(
        select(func.count(ProxyIP.id)).where(ProxyIP.is_active == True)
    )
    active = active_result.scalar()

    # 品質別の数
    quality_stats = {}
    for quality in ProxyQualityEnum:
        result = await db.execute(
            select(func.count(ProxyIP.id)).where(
                and_(
                    ProxyIP.quality == quality,
                    ProxyIP.is_active == True
                )
            )
        )
        quality_stats[quality.value] = result.scalar()

    # レジデンシャルプロキシ数
    residential_result = await db.execute(
        select(func.count(ProxyIP.id)).where(
            and_(
                ProxyIP.is_residential == True,
                ProxyIP.is_active == True
            )
        )
    )
    residential = residential_result.scalar()

    return {
        "total": total,
        "active": active,
        "residential": residential,
        "quality_breakdown": quality_stats
    }
