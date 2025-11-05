'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface OAuthAccount {
  id: number;
  platform: string;
  display_name: string;
  status: string;
  connected_at: string;
  last_used: string | null;
  owner_user_id: number;
}

interface PlatformStatus {
  platform: string;
  name: string;
  logo: string;
  accounts: OAuthAccount[];
  canConnect: boolean;
}

export default function OAuthPage() {
  const [platforms, setPlatforms] = useState<PlatformStatus[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchOAuthStatus();
  }, []);

  const fetchOAuthStatus = async () => {
    try {
      setLoading(true);

      // 各プラットフォームの接続状態を取得
      const platformNames = ['youtube', 'x', 'instagram', 'tiktok'];
      const displayNames = {
        youtube: 'YouTube',
        x: 'X (Twitter)',
        instagram: 'Instagram',
        tiktok: 'TikTok',
      };
      const logos = {
        youtube: '/youtube.png',
        x: '/x.png',
        instagram: '/instagram.png',
        tiktok: '/tiktok.png',
      };

      const platformsData: PlatformStatus[] = [];

      for (const platform of platformNames) {
        try {
          const response = await fetch(`http://localhost:8006/oauth/${platform}/status`);
          const data = await response.json();

          platformsData.push({
            platform,
            name: displayNames[platform as keyof typeof displayNames],
            logo: logos[platform as keyof typeof logos],
            accounts: data.accounts || [],
            canConnect: true,
          });
        } catch (error) {
          console.error(`Failed to fetch ${platform} status:`, error);
          platformsData.push({
            platform,
            name: displayNames[platform as keyof typeof displayNames],
            logo: logos[platform as keyof typeof logos],
            accounts: [],
            canConnect: true,
          });
        }
      }

      setPlatforms(platformsData);
    } catch (error) {
      console.error('Failed to fetch OAuth status:', error);
    } finally {
      setLoading(false);
    }
  };


  const handleConnect = async (platform: string) => {
    try {
      // OAuth接続を開始
      window.location.href = `http://localhost:8006/oauth/${platform}/connect`;
    } catch (error) {
      console.error('Failed to connect:', error);
      alert('接続に失敗しました');
    }
  };

  const handleDisconnect = async (accountId: number, platform: string) => {
    if (!confirm('本当に接続を解除しますか？')) {
      return;
    }

    try {
      const response = await fetch(`http://localhost:8006/oauth/${platform}/disconnect/${accountId}`, {
        method: 'POST',
      });

      const data = await response.json();

      if (data.success) {
        alert('接続を解除しました');
        fetchOAuthStatus();
      } else {
        alert('エラー: ' + (data.error || '接続解除に失敗しました'));
      }
    } catch (error) {
      console.error('Failed to disconnect:', error);
      alert('エラー: 接続解除に失敗しました');
    }
  };

  const handleReauthorize = async (platform: string) => {
    try {
      window.location.href = `http://localhost:8006/oauth/${platform}/connect?reauth=true`;
    } catch (error) {
      console.error('Failed to reauthorize:', error);
      alert('再認可に失敗しました');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-100 text-green-800';
      case 'expired':
        return 'bg-red-100 text-red-800';
      case 'revoked':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-yellow-100 text-yellow-800';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'active':
        return '有効';
      case 'expired':
        return '期限切れ';
      case 'revoked':
        return '取り消し済み';
      default:
        return status;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-muted-foreground">読み込み中...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold">SNS運用オーケストレーター</h1>
          <p className="text-sm text-muted-foreground">v1.3.0</p>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">OAuth接続管理</h2>
            <p className="text-muted-foreground">プラットフォームアカウントの接続状態</p>
          </div>
          <a
            href="/"
            className="px-4 py-2 text-sm border rounded-md hover:bg-accent"
          >
            ← ダッシュボードに戻る
          </a>
        </div>

        <div className="grid gap-6">
          {platforms.map((platform) => (
            <Card key={platform.platform}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="w-12 h-12 relative flex-shrink-0">
                      <Image
                        src={platform.logo}
                        alt={platform.name}
                        fill
                        className="object-contain"
                      />
                    </div>
                    <CardTitle>{platform.name}</CardTitle>
                  </div>
                  <button
                    onClick={() => handleConnect(platform.platform)}
                    className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
                    disabled={!platform.canConnect}
                  >
                    + 新規接続
                  </button>
                </div>
              </CardHeader>
              <CardContent>
                {platform.accounts.length === 0 ? (
                  <div className="py-8 text-center text-muted-foreground">
                    接続されているアカウントはありません
                  </div>
                ) : (
                  <div className="space-y-4">
                    {platform.accounts.map((account) => (
                      <div
                        key={account.id}
                        className="flex items-center justify-between p-4 border rounded-lg"
                      >
                        <div className="flex-1">
                          <div className="flex items-center space-x-3">
                            <h3 className="font-semibold">{account.display_name}</h3>
                            <span
                              className={`text-xs px-2 py-1 rounded ${getStatusColor(
                                account.status
                              )}`}
                            >
                              {getStatusText(account.status)}
                            </span>
                          </div>
                          <div className="mt-2 space-y-1 text-sm text-muted-foreground">
                            <div>
                              アカウントID: {account.id} • オーナー: User {account.owner_user_id}
                            </div>
                            <div>
                              接続日時: {new Date(account.connected_at).toLocaleString('ja-JP')}
                            </div>
                            {account.last_used && (
                              <div>
                                最終利用: {new Date(account.last_used).toLocaleString('ja-JP')}
                              </div>
                            )}
                          </div>
                        </div>

                        <div className="flex space-x-2 ml-4">
                          {account.status === 'expired' && (
                            <button
                              onClick={() => handleReauthorize(platform.platform)}
                              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
                            >
                              再認可
                            </button>
                          )}
                          <button
                            onClick={() => handleDisconnect(account.id, platform.platform)}
                            className="px-4 py-2 text-sm border border-red-600 text-red-600 rounded-md hover:bg-red-50"
                          >
                            接続解除
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>

        {/* 注意事項 */}
        <Card className="mt-8">
          <CardHeader>
            <CardTitle>OAuth接続について</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <h4 className="font-semibold mb-1">接続の流れ</h4>
              <p className="text-muted-foreground">
                「新規接続」ボタンをクリックすると、各プラットフォームの認証画面に遷移します。
                アカウントにログインし、アプリケーションへのアクセスを許可してください。
              </p>
            </div>
            <div>
              <h4 className="font-semibold mb-1">トークンの取り扱い</h4>
              <p className="text-muted-foreground">
                OAuthトークンはKMS封筒方式で暗号化されて保存されます。
                生のトークンは保管されません。
              </p>
            </div>
            <div>
              <h4 className="font-semibold mb-1">有効期限と再認可</h4>
              <p className="text-muted-foreground">
                トークンの有効期限が切れた場合、「再認可」ボタンから再度認証を行ってください。
                自動更新が失敗した場合もこちらから再認可できます。
              </p>
            </div>
            <div>
              <h4 className="font-semibold mb-1">接続解除</h4>
              <p className="text-muted-foreground">
                接続を解除すると、そのアカウントを使用した実行はすべて停止されます。
                実行中のキャンペーンがある場合は注意してください。
              </p>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
