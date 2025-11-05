'use client';

import { useState } from 'react';
import Image from 'next/image';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const PLATFORMS = [
  { id: 'youtube', name: 'YouTube', logo: '/youtube.png' },
  { id: 'x', name: 'X (Twitter)', logo: '/x.png' },
  { id: 'instagram', name: 'Instagram', logo: '/instagram.png' },
  { id: 'tiktok', name: 'TikTok', logo: '/tiktok.png' },
];

const ENGINES = [
  { id: 'api_fast', name: 'API Fast（推奨）', description: '公式API実行' },
  { id: 'browser_qa', name: 'Browser QA（限定）', description: '自社所有ドメインのUI検証用途のみ' },
];

// 16分類監視しきい値のデフォルト値
const DEFAULT_OBSERVABILITY = {
  // 1. IP構造
  ip_ua_inconsistency_sigma: 2.5,
  geo_mismatch_pct: 5,
  asn_bias_pct: 60,
  residential_ratio_min: 30,
  // 2. リズム
  interval_periodicity_score: 75,
  persistent_conn_ratio_min: 40,
  simul_conn_per_ip_max: 4,
  // 3. 暗号
  tls_ja3_mismatch_pct: 3,
  proto_error_rate_pct: 2,
  // 4. UA
  ua_nonexistent_pct: 1,
  ua_per_ip_diversity_min: 1,
  // 5. 指紋
  canvas_hash_drift_sigma: 2.0,
  viewport_ua_mismatch_pct: 5,
  os_browser_consistency_score_min: 80,
  font_plugin_presence_ratio_min: 70,
  // 6. 保存
  cookie_reset_rate_pct: 5,
  localstorage_write_fail_pct: 1,
  // 7. JS
  js_exec_error_pct: 2,
  dom_event_entropy_min: 2.0,
  // 8. ポインタ
  pointer_curve_ratio_min: 30,
  pre_action_delay_ms_min: 150,
  micro_jitter_enabled: true,
  // 9. テンポ
  human_rxn_window_ms: '200-500',
  page_dwell_time_var_pct: 35,
  // 10. 移動
  referrer_consistency_min: 80,
  nav_back_forward_ratio_min: 5,
  // 11. ヘッダ
  header_order_mismatch_pct: 2,
  origin_referer_mismatch_pct: 1,
  content_encoding_error_pct: 1,
  // 12. 送信
  hidden_field_missing_pct: 1,
  burst_api_ratio_pct: 10,
  // 13. CAPTCHA
  post_captcha_hurry_click_ms: 800,
  // 14. 一貫性
  state_consistency_score_min: 85,
  tz_clock_drift_sec_max: 120,
  // 15. 分散
  start_time_spread_minutes: 10,
  burst_cluster_alert_pct: 15,
  // 16. 学習対応
  rule_change_detect_window_min: 30,
  auto_response_policy: 'slowdown',
};

export default function CreateRun() {
  const [platform, setPlatform] = useState('youtube');
  const [engine, setEngine] = useState('api_fast');
  const [accountId, setAccountId] = useState('');
  const [schedule, setSchedule] = useState({
    start: '',
    end: '',
    timezone: 'Asia/Tokyo',
    repeat: 'once',
  });
  const [rateConfig, setRateConfig] = useState({
    hourly_limit: 10,
    daily_limit: 100,
    parallel: 1,
    wait_min_seconds: 60,
    wait_max_seconds: 300,
    distribution: 'normal',
  });
  const [customPrompt, setCustomPrompt] = useState('');
  const [approvalRequired, setApprovalRequired] = useState(true);
  const [observability, setObservability] = useState(DEFAULT_OBSERVABILITY);
  const [showAdvancedObservability, setShowAdvancedObservability] = useState(false);
  const [ipProxyList, setIpProxyList] = useState(''); // IP/Proxyリスト
  const [fixedUAPerIP, setFixedUAPerIP] = useState(true); // 1IP/Proxyに1User-Agent固定
  const [headlessMode, setHeadlessMode] = useState(true); // ヘッドレスモード（画面なし）
  const [retryOnError, setRetryOnError] = useState(true); // エラー時にリトライを実行

  // プラットフォーム別の追加設定
  const [platformSpecific, setPlatformSpecific] = useState({
    // YouTube
    youtube_content_type: 'video', // video, shorts, community
    youtube_visibility: 'public', // public, private, unlisted
    youtube_tags: '',
    youtube_comment_policy: 'enabled',
    // X
    x_type: 'post', // post, thread, quote
    x_mention_management: 'auto',
    x_media_attachments: '',
    // Instagram
    instagram_type: 'feed', // feed, reel
    instagram_location: '',
    instagram_tags: '',
    instagram_reply_policy: 'all',
    // TikTok
    tiktok_caption: '',
    tiktok_sound_id: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const runData = {
      account_id: parseInt(accountId),
      platform,
      engine,
      schedule: {
        start: schedule.start,
        end: schedule.end,
        timezone: schedule.timezone,
        repeat: schedule.repeat,
      },
      rate_config: rateConfig,
      observability_config: {
        ...observability,
        ip_proxy_list: ipProxyList.split('\n').map(ip => ip.trim()).filter(ip => ip.length > 0),
        fixed_ua_per_ip: fixedUAPerIP,
        headless_mode: headlessMode,
        retry_on_error: retryOnError,
      },
      prompt_config: {
        custom_prompt: customPrompt,
      },
      custom_prompt: customPrompt,
      approval_required: approvalRequired,
      platform_specific: platformSpecific,
    };

    try {
      const response = await fetch('http://localhost:8006/runs/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(runData),
      });

      const data = await response.json();

      if (data.success) {
        alert(`実行を作成しました！Run ID: ${data.run_id}`);
        window.location.href = '/runs';
      } else {
        alert('エラー: ' + (data.error || '実行の作成に失敗しました'));
      }
    } catch (error) {
      console.error('Failed to create run:', error);
      alert('エラー: 実行の作成に失敗しました');
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold">SNS運用オーケストレーター</h1>
          <p className="text-sm text-muted-foreground">v1.3.0</p>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h2 className="text-3xl font-bold tracking-tight">実行作成</h2>
          <p className="text-muted-foreground">SNS実行の設定を行います</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* プラットフォーム選択 */}
          <Card>
            <CardHeader>
              <CardTitle>1. プラットフォーム選択</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {PLATFORMS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => setPlatform(p.id)}
                    className={`p-4 border rounded-lg text-center transition-colors ${
                      platform === p.id
                        ? 'border-primary bg-accent'
                        : 'border-border hover:border-primary/50'
                    }`}
                  >
                    <div className="w-12 h-12 relative mx-auto mb-2">
                      <Image
                        src={p.logo}
                        alt={p.name}
                        fill
                        className="object-contain"
                      />
                    </div>
                    <div className="text-sm">{p.name}</div>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* 実行エンジン選択 */}
          <Card>
            <CardHeader>
              <CardTitle>2. 実行エンジン選択</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {ENGINES.map((e) => (
                  <label
                    key={e.id}
                    className={`flex items-start p-4 border rounded-lg cursor-pointer transition-colors ${
                      engine === e.id
                        ? 'border-primary bg-accent'
                        : 'border-border hover:border-primary/50'
                    }`}
                  >
                    <input
                      type="radio"
                      name="engine"
                      value={e.id}
                      checked={engine === e.id}
                      onChange={(ev) => setEngine(ev.target.value)}
                      className="mt-1 mr-3"
                    />
                    <div>
                      <div className="font-medium">{e.name}</div>
                      <div className="text-sm text-muted-foreground">{e.description}</div>
                    </div>
                  </label>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* アカウント選択 */}
          <Card>
            <CardHeader>
              <CardTitle>3. アカウント選択</CardTitle>
            </CardHeader>
            <CardContent>
              <input
                type="number"
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
                placeholder="アカウントIDを入力"
                className="w-full px-4 py-2 border rounded-md"
                required
              />
              <p className="text-sm text-muted-foreground mt-2">
                OAuth接続済みのアカウントIDを入力してください
              </p>
            </CardContent>
          </Card>

          {/* スケジュール設定 */}
          <Card>
            <CardHeader>
              <CardTitle>4. スケジュール設定</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">開始日時</label>
                  <input
                    type="datetime-local"
                    value={schedule.start}
                    onChange={(e) => setSchedule({ ...schedule, start: e.target.value })}
                    className="w-full px-4 py-2 border rounded-md"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">終了日時</label>
                  <input
                    type="datetime-local"
                    value={schedule.end}
                    onChange={(e) => setSchedule({ ...schedule, end: e.target.value })}
                    className="w-full px-4 py-2 border rounded-md"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">タイムゾーン</label>
                <select
                  value={schedule.timezone}
                  onChange={(e) => setSchedule({ ...schedule, timezone: e.target.value })}
                  className="w-full px-4 py-2 border rounded-md"
                >
                  <option value="Asia/Tokyo">Asia/Tokyo</option>
                  <option value="UTC">UTC</option>
                  <option value="America/New_York">America/New_York</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">繰り返し</label>
                <select
                  value={schedule.repeat}
                  onChange={(e) => setSchedule({ ...schedule, repeat: e.target.value })}
                  className="w-full px-4 py-2 border rounded-md"
                >
                  <option value="once">1回のみ</option>
                  <option value="daily">毎日</option>
                  <option value="hourly">毎時</option>
                </select>
              </div>
            </CardContent>
          </Card>

          {/* レート・ペース設定 */}
          <Card>
            <CardHeader>
              <CardTitle>5. レート・ペース設定</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">1時間あたりの上限</label>
                  <input
                    type="number"
                    value={rateConfig.hourly_limit}
                    onChange={(e) =>
                      setRateConfig({ ...rateConfig, hourly_limit: parseInt(e.target.value) })
                    }
                    className="w-full px-4 py-2 border rounded-md"
                    min="1"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">1日あたりの上限</label>
                  <input
                    type="number"
                    value={rateConfig.daily_limit}
                    onChange={(e) =>
                      setRateConfig({ ...rateConfig, daily_limit: parseInt(e.target.value) })
                    }
                    className="w-full px-4 py-2 border rounded-md"
                    min="1"
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">並列数</label>
                  <input
                    type="number"
                    value={rateConfig.parallel}
                    onChange={(e) =>
                      setRateConfig({ ...rateConfig, parallel: parseInt(e.target.value) })
                    }
                    className="w-full px-4 py-2 border rounded-md"
                    min="1"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">最小待機時間（秒）</label>
                  <input
                    type="number"
                    value={rateConfig.wait_min_seconds}
                    onChange={(e) =>
                      setRateConfig({ ...rateConfig, wait_min_seconds: parseInt(e.target.value) })
                    }
                    className="w-full px-4 py-2 border rounded-md"
                    min="1"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">最大待機時間（秒）</label>
                  <input
                    type="number"
                    value={rateConfig.wait_max_seconds}
                    onChange={(e) =>
                      setRateConfig({ ...rateConfig, wait_max_seconds: parseInt(e.target.value) })
                    }
                    className="w-full px-4 py-2 border rounded-md"
                    min="1"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">待機時間の分布</label>
                <select
                  value={rateConfig.distribution}
                  onChange={(e) => setRateConfig({ ...rateConfig, distribution: e.target.value })}
                  className="w-full px-4 py-2 border rounded-md"
                >
                  <option value="uniform">Uniform（均等）</option>
                  <option value="normal">Normal（正規分布）</option>
                </select>
              </div>
            </CardContent>
          </Card>

          {/* プラットフォーム別設定 */}
          <Card>
            <CardHeader>
              <CardTitle>6. プラットフォーム別設定</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {platform === 'youtube' && (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-2">コンテンツタイプ</label>
                    <select
                      value={platformSpecific.youtube_content_type}
                      onChange={(e) =>
                        setPlatformSpecific({ ...platformSpecific, youtube_content_type: e.target.value })
                      }
                      className="w-full px-4 py-2 border rounded-md"
                    >
                      <option value="video">動画</option>
                      <option value="shorts">Shorts</option>
                      <option value="community">コミュニティ投稿</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">公開範囲</label>
                    <select
                      value={platformSpecific.youtube_visibility}
                      onChange={(e) =>
                        setPlatformSpecific({ ...platformSpecific, youtube_visibility: e.target.value })
                      }
                      className="w-full px-4 py-2 border rounded-md"
                    >
                      <option value="public">公開</option>
                      <option value="unlisted">限定公開</option>
                      <option value="private">非公開</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">タグ（カンマ区切り）</label>
                    <input
                      type="text"
                      value={platformSpecific.youtube_tags}
                      onChange={(e) =>
                        setPlatformSpecific({ ...platformSpecific, youtube_tags: e.target.value })
                      }
                      placeholder="例: tech, tutorial, programming"
                      className="w-full px-4 py-2 border rounded-md"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">コメント方針</label>
                    <select
                      value={platformSpecific.youtube_comment_policy}
                      onChange={(e) =>
                        setPlatformSpecific({ ...platformSpecific, youtube_comment_policy: e.target.value })
                      }
                      className="w-full px-4 py-2 border rounded-md"
                    >
                      <option value="enabled">有効</option>
                      <option value="disabled">無効</option>
                      <option value="approval">承認制</option>
                    </select>
                  </div>
                </>
              )}
              {platform === 'x' && (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-2">投稿タイプ</label>
                    <select
                      value={platformSpecific.x_type}
                      onChange={(e) => setPlatformSpecific({ ...platformSpecific, x_type: e.target.value })}
                      className="w-full px-4 py-2 border rounded-md"
                    >
                      <option value="post">通常投稿</option>
                      <option value="thread">スレッド</option>
                      <option value="quote">引用</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">メンション管理</label>
                    <select
                      value={platformSpecific.x_mention_management}
                      onChange={(e) =>
                        setPlatformSpecific({ ...platformSpecific, x_mention_management: e.target.value })
                      }
                      className="w-full px-4 py-2 border rounded-md"
                    >
                      <option value="auto">自動</option>
                      <option value="manual">手動承認</option>
                      <option value="off">無効</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">メディア添付（URL）</label>
                    <input
                      type="text"
                      value={platformSpecific.x_media_attachments}
                      onChange={(e) =>
                        setPlatformSpecific({ ...platformSpecific, x_media_attachments: e.target.value })
                      }
                      placeholder="画像・動画のURL"
                      className="w-full px-4 py-2 border rounded-md"
                    />
                  </div>
                </>
              )}
              {platform === 'instagram' && (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-2">コンテンツタイプ</label>
                    <select
                      value={platformSpecific.instagram_type}
                      onChange={(e) =>
                        setPlatformSpecific({ ...platformSpecific, instagram_type: e.target.value })
                      }
                      className="w-full px-4 py-2 border rounded-md"
                    >
                      <option value="feed">フィード</option>
                      <option value="reel">リール</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">ロケーション</label>
                    <input
                      type="text"
                      value={platformSpecific.instagram_location}
                      onChange={(e) =>
                        setPlatformSpecific({ ...platformSpecific, instagram_location: e.target.value })
                      }
                      placeholder="場所を入力"
                      className="w-full px-4 py-2 border rounded-md"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">タグ（カンマ区切り）</label>
                    <input
                      type="text"
                      value={platformSpecific.instagram_tags}
                      onChange={(e) =>
                        setPlatformSpecific({ ...platformSpecific, instagram_tags: e.target.value })
                      }
                      placeholder="例: #travel, #food"
                      className="w-full px-4 py-2 border rounded-md"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">返信方針</label>
                    <select
                      value={platformSpecific.instagram_reply_policy}
                      onChange={(e) =>
                        setPlatformSpecific({ ...platformSpecific, instagram_reply_policy: e.target.value })
                      }
                      className="w-full px-4 py-2 border rounded-md"
                    >
                      <option value="all">すべて</option>
                      <option value="followers">フォロワーのみ</option>
                      <option value="none">なし</option>
                    </select>
                  </div>
                </>
              )}
              {platform === 'tiktok' && (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-2">字幕</label>
                    <textarea
                      value={platformSpecific.tiktok_caption}
                      onChange={(e) =>
                        setPlatformSpecific({ ...platformSpecific, tiktok_caption: e.target.value })
                      }
                      placeholder="動画の字幕を入力"
                      className="w-full px-4 py-2 border rounded-md min-h-[80px]"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">サウンドID（オプション）</label>
                    <input
                      type="text"
                      value={platformSpecific.tiktok_sound_id}
                      onChange={(e) =>
                        setPlatformSpecific({ ...platformSpecific, tiktok_sound_id: e.target.value })
                      }
                      placeholder="権利範囲内のサウンドID"
                      className="w-full px-4 py-2 border rounded-md"
                    />
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* 16分類監視しきい値 */}
          <Card>
            <CardHeader>
              <CardTitle>7. Bot検知回避・監視設定</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* IP/Proxyリスト */}
              <div>
                <label className="block text-sm font-medium mb-2">
                  使用IP/Proxyリスト（1行に1つ）
                </label>
                <textarea
                  value={ipProxyList}
                  onChange={(e) => setIpProxyList(e.target.value)}
                  placeholder={'例:\n123.45.67.89\nproxy1.example.com:8080\n98.76.54.32\n103.20.30.40'}
                  className="w-full px-4 py-2 border rounded-md min-h-[120px] font-mono text-sm"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  使用するIPアドレスまたはProxyを1行に1つずつ入力。空欄の場合はデフォルトIPを使用します。
                </p>
              </div>

              {/* ブラウザ実行モード設定 */}
              <div className="space-y-3">
                {/* ヘッドレスモード設定 */}
                <div className="border rounded-lg p-4 bg-accent/30">
                  <label className="flex items-start space-x-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={headlessMode}
                      onChange={(e) => setHeadlessMode(e.target.checked)}
                      className="w-4 h-4 mt-1"
                    />
                    <div className="flex-1">
                      <div className="font-medium text-sm">
                        ヘッドレスモード（画面なし）で実行する（推奨）
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        <p className="mb-1">
                          <strong>✓ 有効（推奨）:</strong> ブラウザ画面を表示せずにバックグラウンドで実行します。
                          リソース消費が少なく、高速で動作します。本番運用に最適です。
                        </p>
                        <p>
                          <strong>✗ 無効（画面付き）:</strong> 実際のブラウザ画面を表示しながら実行します。
                          動作確認やデバッグ、QAテスト時に有効です。リソース消費が大きくなります。
                        </p>
                      </div>
                    </div>
                  </label>
                </div>

                {/* User-Agent固定設定 */}
                <div className="border rounded-lg p-4 bg-accent/30">
                  <label className="flex items-start space-x-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={fixedUAPerIP}
                      onChange={(e) => setFixedUAPerIP(e.target.checked)}
                      className="w-4 h-4 mt-1"
                    />
                    <div className="flex-1">
                      <div className="font-medium text-sm">
                        1つのIP/Proxyに対して1つのUser-Agentを固定する（推奨）
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        <p className="mb-1">
                          <strong>✓ 有効（推奨）:</strong> 各IP/Proxyごとに同じUser-Agentを使い続けます。
                          より自然なアクセスパターンとなり、Bot検知を回避しやすくなります。
                        </p>
                        <p>
                          <strong>✗ 無効:</strong> 同じIP/Proxyでも毎回異なるUser-Agentを使用します。
                          IPとブラウザ情報の不整合が発生し、検知されやすくなる可能性があります。
                        </p>
                      </div>
                    </div>
                  </label>
                </div>

                {/* リトライ設定 */}
                <div className="border rounded-lg p-4 bg-accent/30">
                  <label className="flex items-start space-x-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={retryOnError}
                      onChange={(e) => setRetryOnError(e.target.checked)}
                      className="w-4 h-4 mt-1"
                    />
                    <div className="flex-1">
                      <div className="font-medium text-sm">
                        エラー時にリトライを自動実行する（推奨）
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        <p className="mb-1">
                          <strong>✓ 有効（推奨）:</strong> ネットワークエラーや一時的な障害が発生した場合、
                          指数バックオフ（徐々に間隔を広げる）を使って自動的にリトライします。
                          一時的な問題を自動復旧し、実行成功率が向上します。
                        </p>
                        <p>
                          <strong>✗ 無効:</strong> エラーが発生した場合、即座に失敗として処理します。
                          リトライせずに停止するため、手動での再実行が必要になります。
                          デバッグ時やエラー原因を即座に確認したい場合に使用します。
                        </p>
                      </div>
                    </div>
                  </label>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setShowAdvancedObservability(!showAdvancedObservability)}
                className="w-full px-4 py-2 text-sm font-medium text-left border rounded-md hover:bg-accent"
              >
                {showAdvancedObservability ? '▼ 詳細な監視設定を非表示' : '▶ 詳細な監視設定を表示（通常は変更不要）'}
              </button>

              {showAdvancedObservability && (
                <div className="mt-4 space-y-6">
                  {/* 1. IP構造 */}
                  <div className="border-t pt-4">
                    <h4 className="font-semibold mb-2">1. IPアドレス・アクセス元の管理</h4>
                    <p className="text-xs text-muted-foreground mb-3">
                      同じIPから不自然なアクセスパターンを避けるための設定
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm mb-1">
                          IPとブラウザ情報の整合性チェック（標準偏差）
                        </label>
                        <input
                          type="number"
                          step="0.1"
                          value={observability.ip_ua_inconsistency_sigma}
                          onChange={(e) =>
                            setObservability({
                              ...observability,
                              ip_ua_inconsistency_sigma: parseFloat(e.target.value),
                            })
                          }
                          className="w-full px-3 py-1 text-sm border rounded-md"
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                          推奨: 2.5（低いほど厳格）
                        </p>
                      </div>
                      <div>
                        <label className="block text-sm mb-1">地域不一致の許容率 (%)</label>
                        <input
                          type="number"
                          value={observability.geo_mismatch_pct}
                          onChange={(e) =>
                            setObservability({ ...observability, geo_mismatch_pct: parseInt(e.target.value) })
                          }
                          className="w-full px-3 py-1 text-sm border rounded-md"
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                          推奨: 5%（IPの国とアカウント設定が異なる割合）
                        </p>
                      </div>
                      <div>
                        <label className="block text-sm mb-1">同一ISPからの集中アクセス上限 (%)</label>
                        <input
                          type="number"
                          value={observability.asn_bias_pct}
                          onChange={(e) =>
                            setObservability({ ...observability, asn_bias_pct: parseInt(e.target.value) })
                          }
                          className="w-full px-3 py-1 text-sm border rounded-md"
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                          推奨: 60%（偏りすぎると不自然）
                        </p>
                      </div>
                      <div>
                        <label className="block text-sm mb-1">一般回線・モバイル回線の最低比率 (%)</label>
                        <input
                          type="number"
                          value={observability.residential_ratio_min}
                          onChange={(e) =>
                            setObservability({
                              ...observability,
                              residential_ratio_min: parseInt(e.target.value),
                            })
                          }
                          className="w-full px-3 py-1 text-sm border rounded-md"
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                          推奨: 30%（データセンターIPばかりだと検知される）
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* 2. リズム */}
                  <div className="border-t pt-4">
                    <h4 className="font-semibold mb-2">2. アクセス間隔・タイミングの自然さ</h4>
                    <p className="text-xs text-muted-foreground mb-3">
                      規則的すぎる操作や、短時間に大量アクセスを避けるための設定
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm mb-1">アクション間隔の規則性チェック (0-100)</label>
                        <input
                          type="number"
                          value={observability.interval_periodicity_score}
                          onChange={(e) =>
                            setObservability({
                              ...observability,
                              interval_periodicity_score: parseInt(e.target.value),
                            })
                          }
                          className="w-full px-3 py-1 text-sm border rounded-md"
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                          推奨: 75（高いほど不規則な間隔を許容）
                        </p>
                      </div>
                      <div>
                        <label className="block text-sm mb-1">接続を維持する割合の下限 (%)</label>
                        <input
                          type="number"
                          value={observability.persistent_conn_ratio_min}
                          onChange={(e) =>
                            setObservability({
                              ...observability,
                              persistent_conn_ratio_min: parseInt(e.target.value),
                            })
                          }
                          className="w-full px-3 py-1 text-sm border rounded-md"
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                          推奨: 40%（毎回切断すると不自然）
                        </p>
                      </div>
                      <div>
                        <label className="block text-sm mb-1">1つのIPで同時実行できる上限数</label>
                        <input
                          type="number"
                          value={observability.simul_conn_per_ip_max}
                          onChange={(e) =>
                            setObservability({
                              ...observability,
                              simul_conn_per_ip_max: parseInt(e.target.value),
                            })
                          }
                          className="w-full px-3 py-1 text-sm border rounded-md"
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                          推奨: 4（同じIPから複数アクセスしすぎない）
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* 3-16分類の残りを簡略表示 */}
                  <div className="border-t pt-4">
                    <h4 className="font-semibold mb-2">3-16. その他の高度な監視項目</h4>
                    <p className="text-sm text-muted-foreground mb-3">
                      通信の暗号化、ブラウザ情報、マウス操作、画面遷移など、Bot検知システムが見ている細かい項目の設定です。
                      通常はデフォルト値で問題ありません。
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                      <div>
                        <label className="block mb-1"><span className="font-medium">通信暗号化の不一致率上限 (%)</span></label>
                        <input
                          type="number"
                          value={observability.tls_ja3_mismatch_pct}
                          onChange={(e) =>
                            setObservability({
                              ...observability,
                              tls_ja3_mismatch_pct: parseInt(e.target.value),
                            })
                          }
                          className="w-full px-2 py-1 border rounded"
                        />
                        <p className="text-muted-foreground mt-0.5">推奨: 3%</p>
                      </div>
                      <div>
                        <label className="block mb-1"><span className="font-medium">偽装ブラウザ検知率上限 (%)</span></label>
                        <input
                          type="number"
                          value={observability.ua_nonexistent_pct}
                          onChange={(e) =>
                            setObservability({ ...observability, ua_nonexistent_pct: parseInt(e.target.value) })
                          }
                          className="w-full px-2 py-1 border rounded"
                        />
                        <p className="text-muted-foreground mt-0.5">推奨: 1%</p>
                      </div>
                      <div>
                        <label className="block mb-1"><span className="font-medium">画面表示の変動チェック</span></label>
                        <input
                          type="number"
                          step="0.1"
                          value={observability.canvas_hash_drift_sigma}
                          onChange={(e) =>
                            setObservability({
                              ...observability,
                              canvas_hash_drift_sigma: parseFloat(e.target.value),
                            })
                          }
                          className="w-full px-2 py-1 border rounded"
                        />
                        <p className="text-muted-foreground mt-0.5">推奨: 2.0</p>
                      </div>
                      <div>
                        <label className="block mb-1"><span className="font-medium">Cookie削除頻度上限 (%)</span></label>
                        <input
                          type="number"
                          value={observability.cookie_reset_rate_pct}
                          onChange={(e) =>
                            setObservability({
                              ...observability,
                              cookie_reset_rate_pct: parseInt(e.target.value),
                            })
                          }
                          className="w-full px-2 py-1 border rounded"
                        />
                        <p className="text-muted-foreground mt-0.5">推奨: 5%</p>
                      </div>
                      <div>
                        <label className="block mb-1"><span className="font-medium">JavaScriptエラー率上限 (%)</span></label>
                        <input
                          type="number"
                          value={observability.js_exec_error_pct}
                          onChange={(e) =>
                            setObservability({ ...observability, js_exec_error_pct: parseInt(e.target.value) })
                          }
                          className="w-full px-2 py-1 border rounded"
                        />
                        <p className="text-muted-foreground mt-0.5">推奨: 2%</p>
                      </div>
                      <div>
                        <label className="block mb-1"><span className="font-medium">マウス曲線動作の最低割合 (%)</span></label>
                        <input
                          type="number"
                          value={observability.pointer_curve_ratio_min}
                          onChange={(e) =>
                            setObservability({
                              ...observability,
                              pointer_curve_ratio_min: parseInt(e.target.value),
                            })
                          }
                          className="w-full px-2 py-1 border rounded"
                        />
                        <p className="text-muted-foreground mt-0.5">推奨: 30%（直線的すぎない）</p>
                      </div>
                      <div>
                        <label className="block mb-1"><span className="font-medium">ページ滞在時間の変動率 (%)</span></label>
                        <input
                          type="number"
                          value={observability.page_dwell_time_var_pct}
                          onChange={(e) =>
                            setObservability({
                              ...observability,
                              page_dwell_time_var_pct: parseInt(e.target.value),
                            })
                          }
                          className="w-full px-2 py-1 border rounded"
                        />
                        <p className="text-muted-foreground mt-0.5">推奨: 35%</p>
                      </div>
                      <div>
                        <label className="block mb-1"><span className="font-medium">参照元URLの整合性下限</span></label>
                        <input
                          type="number"
                          value={observability.referrer_consistency_min}
                          onChange={(e) =>
                            setObservability({
                              ...observability,
                              referrer_consistency_min: parseInt(e.target.value),
                            })
                          }
                          className="w-full px-2 py-1 border rounded"
                        />
                        <p className="text-muted-foreground mt-0.5">推奨: 80</p>
                      </div>
                      <div>
                        <label className="block mb-1"><span className="font-medium">HTTPヘッダ順序の不一致上限 (%)</span></label>
                        <input
                          type="number"
                          value={observability.header_order_mismatch_pct}
                          onChange={(e) =>
                            setObservability({
                              ...observability,
                              header_order_mismatch_pct: parseInt(e.target.value),
                            })
                          }
                          className="w-full px-2 py-1 border rounded"
                        />
                        <p className="text-muted-foreground mt-0.5">推奨: 2%</p>
                      </div>
                      <div>
                        <label className="block mb-1"><span className="font-medium">API集中アクセス率上限 (%)</span></label>
                        <input
                          type="number"
                          value={observability.burst_api_ratio_pct}
                          onChange={(e) =>
                            setObservability({
                              ...observability,
                              burst_api_ratio_pct: parseInt(e.target.value),
                            })
                          }
                          className="w-full px-2 py-1 border rounded"
                        />
                        <p className="text-muted-foreground mt-0.5">推奨: 10%</p>
                      </div>
                      <div>
                        <label className="block mb-1"><span className="font-medium">CAPTCHA後の最短クリック時間 (ms)</span></label>
                        <input
                          type="number"
                          value={observability.post_captcha_hurry_click_ms}
                          onChange={(e) =>
                            setObservability({
                              ...observability,
                              post_captcha_hurry_click_ms: parseInt(e.target.value),
                            })
                          }
                          className="w-full px-2 py-1 border rounded"
                        />
                        <p className="text-muted-foreground mt-0.5">推奨: 800ms（速すぎると不自然）</p>
                      </div>
                      <div>
                        <label className="block mb-1"><span className="font-medium">セッション状態の整合性下限</span></label>
                        <input
                          type="number"
                          value={observability.state_consistency_score_min}
                          onChange={(e) =>
                            setObservability({
                              ...observability,
                              state_consistency_score_min: parseInt(e.target.value),
                            })
                          }
                          className="w-full px-2 py-1 border rounded"
                        />
                        <p className="text-muted-foreground mt-0.5">推奨: 85</p>
                      </div>
                      <div>
                        <label className="block mb-1"><span className="font-medium">開始時刻の分散幅 (分)</span></label>
                        <input
                          type="number"
                          value={observability.start_time_spread_minutes}
                          onChange={(e) =>
                            setObservability({
                              ...observability,
                              start_time_spread_minutes: parseInt(e.target.value),
                            })
                          }
                          className="w-full px-2 py-1 border rounded"
                        />
                        <p className="text-muted-foreground mt-0.5">推奨: 10分（同時開始を避ける）</p>
                      </div>
                      <div>
                        <label className="block mb-1"><span className="font-medium">プラットフォーム変更検知の窓 (分)</span></label>
                        <input
                          type="number"
                          value={observability.rule_change_detect_window_min}
                          onChange={(e) =>
                            setObservability({
                              ...observability,
                              rule_change_detect_window_min: parseInt(e.target.value),
                            })
                          }
                          className="w-full px-2 py-1 border rounded"
                        />
                        <p className="text-muted-foreground mt-0.5">推奨: 30分</p>
                      </div>
                      <div>
                        <label className="block mb-1"><span className="font-medium">違反検知時の自動対応</span></label>
                        <select
                          value={observability.auto_response_policy}
                          onChange={(e) =>
                            setObservability({ ...observability, auto_response_policy: e.target.value })
                          }
                          className="w-full px-2 py-1 border rounded text-xs"
                        >
                          <option value="alert">通知のみ</option>
                          <option value="slowdown">速度を落とす</option>
                          <option value="freeze">一時停止</option>
                          <option value="abort">即座に中止</option>
                        </select>
                        <p className="text-muted-foreground mt-0.5">推奨: 速度を落とす</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Custom Prompt */}
          <Card>
            <CardHeader>
              <CardTitle>8. カスタムプロンプト（シナリオ設計）</CardTitle>
            </CardHeader>
            <CardContent>
              <textarea
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                placeholder="AIに指示するカスタムプロンプトを入力してください（オプション）"
                className="w-full px-4 py-2 border rounded-md min-h-[120px]"
              />
              <p className="text-sm text-muted-foreground mt-2">
                安全フィルタを通過する必要があります
              </p>
            </CardContent>
          </Card>

          {/* 承認設定 */}
          <Card>
            <CardHeader>
              <CardTitle>9. 承認設定</CardTitle>
            </CardHeader>
            <CardContent>
              <label className="flex items-center space-x-3">
                <input
                  type="checkbox"
                  checked={approvalRequired}
                  onChange={(e) => setApprovalRequired(e.target.checked)}
                  className="w-4 h-4"
                />
                <span>返信系の承認を必須にする（推奨）</span>
              </label>
            </CardContent>
          </Card>

          {/* 送信ボタン */}
          <div className="flex justify-end space-x-4">
            <button
              type="button"
              onClick={() => (window.location.href = '/')}
              className="px-6 py-2 border rounded-md hover:bg-accent"
            >
              キャンセル
            </button>
            <button
              type="submit"
              className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              実行を作成
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
