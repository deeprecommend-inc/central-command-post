'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface Campaign {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  target_metrics: {
    target_posts?: number;
    target_engagements?: number;
    target_followers?: number;
    custom_kpis?: { [key: string]: number };
  };
  run_ids: number[];
  status: string;
  created_at: string;
}

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);

  // 新規作成フォームの状態
  const [formData, setFormData] = useState({
    name: '',
    start_date: '',
    end_date: '',
    target_posts: 0,
    target_engagements: 0,
    target_followers: 0,
    run_ids: '',
  });

  useEffect(() => {
    fetchCampaigns();
  }, []);

  const fetchCampaigns = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8006/campaigns/');
      const data = await response.json();
      setCampaigns(data.campaigns || []);
    } catch (error) {
      console.error('Failed to fetch campaigns:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();

    const campaignData = {
      name: formData.name,
      start_date: formData.start_date,
      end_date: formData.end_date,
      target_metrics: {
        target_posts: formData.target_posts,
        target_engagements: formData.target_engagements,
        target_followers: formData.target_followers,
      },
      run_ids: formData.run_ids
        .split(',')
        .map((id) => parseInt(id.trim()))
        .filter((id) => !isNaN(id)),
    };

    try {
      const response = await fetch('http://localhost:8006/campaigns/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(campaignData),
      });

      const data = await response.json();

      if (data.success) {
        alert('キャンペーンを作成しました！');
        setShowCreateForm(false);
        setFormData({
          name: '',
          start_date: '',
          end_date: '',
          target_posts: 0,
          target_engagements: 0,
          target_followers: 0,
          run_ids: '',
        });
        fetchCampaigns();
      } else {
        alert('エラー: ' + (data.error || 'キャンペーンの作成に失敗しました'));
      }
    } catch (error) {
      console.error('Failed to create campaign:', error);
      alert('エラー: キャンペーンの作成に失敗しました');
    }
  };

  const handleDelete = async (campaignId: number) => {
    if (!confirm('このキャンペーンを削除しますか？関連する実行は削除されません。')) {
      return;
    }

    try {
      const response = await fetch(`http://localhost:8006/campaigns/${campaignId}`, {
        method: 'DELETE',
      });

      const data = await response.json();

      if (data.success) {
        alert('キャンペーンを削除しました');
        fetchCampaigns();
      } else {
        alert('エラー: ' + (data.error || '削除に失敗しました'));
      }
    } catch (error) {
      console.error('Failed to delete campaign:', error);
      alert('エラー: 削除に失敗しました');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-100 text-green-800';
      case 'scheduled':
        return 'bg-blue-100 text-blue-800';
      case 'completed':
        return 'bg-gray-100 text-gray-800';
      case 'paused':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'active':
        return '実行中';
      case 'scheduled':
        return '予定';
      case 'completed':
        return '完了';
      case 'paused':
        return '一時停止';
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
            <h2 className="text-3xl font-bold tracking-tight">キャンペーン管理</h2>
            <p className="text-muted-foreground">期間・目標・対象投稿束の管理</p>
          </div>
          <div className="flex space-x-3">
            <a
              href="/"
              className="px-4 py-2 text-sm border rounded-md hover:bg-accent"
            >
              ← ダッシュボードに戻る
            </a>
            <button
              onClick={() => setShowCreateForm(true)}
              className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              + 新規キャンペーン
            </button>
          </div>
        </div>

        {/* キャンペーン一覧 */}
        {campaigns.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center text-muted-foreground">
              キャンペーンはまだありません
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-6">
            {campaigns.map((campaign) => (
              <Card key={campaign.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <CardTitle>{campaign.name}</CardTitle>
                      <span className={`text-xs px-2 py-1 rounded ${getStatusColor(campaign.status)}`}>
                        {getStatusText(campaign.status)}
                      </span>
                    </div>
                    <button
                      onClick={() => handleDelete(campaign.id)}
                      className="px-3 py-1 text-sm border border-red-600 text-red-600 rounded-md hover:bg-red-50"
                    >
                      削除
                    </button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* 期間 */}
                    <div>
                      <h4 className="font-semibold mb-2">期間</h4>
                      <div className="space-y-1 text-sm">
                        <div>
                          開始: {new Date(campaign.start_date).toLocaleString('ja-JP')}
                        </div>
                        <div>
                          終了: {new Date(campaign.end_date).toLocaleString('ja-JP')}
                        </div>
                        <div className="text-muted-foreground">
                          作成: {new Date(campaign.created_at).toLocaleString('ja-JP')}
                        </div>
                      </div>
                    </div>

                    {/* 目標 */}
                    <div>
                      <h4 className="font-semibold mb-2">目標KPI</h4>
                      <div className="space-y-1 text-sm">
                        {campaign.target_metrics.target_posts !== undefined && (
                          <div className="flex justify-between">
                            <span>目標投稿数:</span>
                            <span className="font-semibold">{campaign.target_metrics.target_posts}</span>
                          </div>
                        )}
                        {campaign.target_metrics.target_engagements !== undefined && (
                          <div className="flex justify-between">
                            <span>目標エンゲージメント:</span>
                            <span className="font-semibold">{campaign.target_metrics.target_engagements}</span>
                          </div>
                        )}
                        {campaign.target_metrics.target_followers !== undefined && (
                          <div className="flex justify-between">
                            <span>目標フォロワー数:</span>
                            <span className="font-semibold">{campaign.target_metrics.target_followers}</span>
                          </div>
                        )}
                        {campaign.target_metrics.custom_kpis &&
                          Object.entries(campaign.target_metrics.custom_kpis).map(([key, value]) => (
                            <div key={key} className="flex justify-between">
                              <span>{key}:</span>
                              <span className="font-semibold">{value}</span>
                            </div>
                          ))}
                      </div>
                    </div>

                    {/* 対象実行 */}
                    <div className="md:col-span-2">
                      <h4 className="font-semibold mb-2">対象実行 ({campaign.run_ids.length}件)</h4>
                      {campaign.run_ids.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {campaign.run_ids.map((runId) => (
                            <a
                              key={runId}
                              href={`/runs/${runId}`}
                              className="px-3 py-1 text-sm bg-accent rounded-md hover:bg-accent/80"
                            >
                              Run #{runId}
                            </a>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">実行が関連付けられていません</p>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* 新規作成フォーム */}
        {showCreateForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
            <Card className="max-w-2xl w-full max-h-[90vh] overflow-y-auto">
              <CardHeader>
                <CardTitle>新規キャンペーン作成</CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleCreate} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">キャンペーン名</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      placeholder="例: 2025年春キャンペーン"
                      className="w-full px-4 py-2 border rounded-md"
                      required
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium mb-2">開始日時</label>
                      <input
                        type="datetime-local"
                        value={formData.start_date}
                        onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                        className="w-full px-4 py-2 border rounded-md"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-2">終了日時</label>
                      <input
                        type="datetime-local"
                        value={formData.end_date}
                        onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                        className="w-full px-4 py-2 border rounded-md"
                        required
                      />
                    </div>
                  </div>

                  <div>
                    <h4 className="font-semibold mb-3">目標設定</h4>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div>
                        <label className="block text-sm mb-2">目標投稿数</label>
                        <input
                          type="number"
                          value={formData.target_posts}
                          onChange={(e) =>
                            setFormData({ ...formData, target_posts: parseInt(e.target.value) })
                          }
                          className="w-full px-4 py-2 border rounded-md"
                          min="0"
                        />
                      </div>
                      <div>
                        <label className="block text-sm mb-2">目標エンゲージメント</label>
                        <input
                          type="number"
                          value={formData.target_engagements}
                          onChange={(e) =>
                            setFormData({ ...formData, target_engagements: parseInt(e.target.value) })
                          }
                          className="w-full px-4 py-2 border rounded-md"
                          min="0"
                        />
                      </div>
                      <div>
                        <label className="block text-sm mb-2">目標フォロワー増</label>
                        <input
                          type="number"
                          value={formData.target_followers}
                          onChange={(e) =>
                            setFormData({ ...formData, target_followers: parseInt(e.target.value) })
                          }
                          className="w-full px-4 py-2 border rounded-md"
                          min="0"
                        />
                      </div>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2">
                      対象実行ID（カンマ区切り）
                    </label>
                    <input
                      type="text"
                      value={formData.run_ids}
                      onChange={(e) => setFormData({ ...formData, run_ids: e.target.value })}
                      placeholder="例: 1, 2, 5, 10"
                      className="w-full px-4 py-2 border rounded-md"
                    />
                    <p className="text-sm text-muted-foreground mt-1">
                      このキャンペーンに関連付ける実行のIDをカンマ区切りで入力
                    </p>
                  </div>

                  <div className="flex space-x-3 pt-4">
                    <button
                      type="submit"
                      className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
                    >
                      作成
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setShowCreateForm(false);
                        setFormData({
                          name: '',
                          start_date: '',
                          end_date: '',
                          target_posts: 0,
                          target_engagements: 0,
                          target_followers: 0,
                          run_ids: '',
                        });
                      }}
                      className="px-4 py-2 border rounded-md hover:bg-accent"
                    >
                      キャンセル
                    </button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}
