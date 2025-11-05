'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface ObservabilityMetric {
  id: number;
  run_id: number;
  category: string;
  metric_key: string;
  metric_value: number;
  threshold_value: number;
  violated: boolean;
  action_taken: string;
  timestamp: string;
}

interface ActiveRun {
  id: number;
  platform: string;
  status: string;
  started_at: string;
}

const OBSERVABILITY_CATEGORIES = [
  { id: 1, name: 'IP構造', key: 'ip_structure' },
  { id: 2, name: '通信リズム', key: 'rhythm' },
  { id: 3, name: '暗号/プロトコル', key: 'tls' },
  { id: 4, name: 'UA', key: 'ua' },
  { id: 5, name: '指紋', key: 'fingerprint' },
  { id: 6, name: 'Cookie/保存', key: 'storage' },
  { id: 7, name: 'JS動作', key: 'js' },
  { id: 8, name: 'マウス/クリック', key: 'pointer' },
  { id: 9, name: 'テンポ', key: 'tempo' },
  { id: 10, name: 'ナビゲーション', key: 'navigation' },
  { id: 11, name: 'ヘッダ', key: 'headers' },
  { id: 12, name: 'データ送信', key: 'transmission' },
  { id: 13, name: 'CAPTCHA', key: 'captcha' },
  { id: 14, name: '一貫性', key: 'consistency' },
  { id: 15, name: '分散', key: 'distribution' },
  { id: 16, name: '学習対応', key: 'auto_learning' },
];

export default function MonitoringPage() {
  const [metrics, setMetrics] = useState<ObservabilityMetric[]>([]);
  const [activeRuns, setActiveRuns] = useState<ActiveRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    fetchData();

    if (autoRefresh) {
      const interval = setInterval(fetchData, 10000); // 10秒ごとに更新
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const fetchData = async () => {
    try {
      setLoading(true);

      // 監視メトリクスを取得
      const metricsResponse = await fetch('http://localhost:8006/metrics/observability');
      const metricsData = await metricsResponse.json();
      setMetrics(metricsData.metrics || []);

      // アクティブな実行を取得
      const runsResponse = await fetch('http://localhost:8006/runs/?status=active');
      const runsData = await runsResponse.json();
      setActiveRuns(runsData.runs || []);
    } catch (error) {
      console.error('Failed to fetch monitoring data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleKillSwitch = async (runId: number) => {
    if (!confirm(`実行 #${runId} を緊急停止しますか？この操作は取り消せません。`)) {
      return;
    }

    const reason = prompt('停止理由を入力してください（必須）');
    if (!reason) {
      return;
    }

    try {
      const response = await fetch(`http://localhost:8006/runs/${runId}/kill`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ reason }),
      });

      const data = await response.json();

      if (data.success) {
        alert('実行を緊急停止しました');
        fetchData();
      } else {
        alert('エラー: ' + (data.error || '停止に失敗しました'));
      }
    } catch (error) {
      console.error('Failed to kill run:', error);
      alert('エラー: 停止に失敗しました');
    }
  };

  const filteredMetrics =
    selectedCategory === 'all'
      ? metrics
      : metrics.filter((m) => m.category === selectedCategory);

  const violationCount = metrics.filter((m) => m.violated).length;
  const criticalCount = metrics.filter((m) => m.violated && m.action_taken === 'abort').length;

  const getActionColor = (action: string) => {
    switch (action) {
      case 'abort':
        return 'bg-red-600 text-white';
      case 'freeze':
        return 'bg-orange-600 text-white';
      case 'slow':
        return 'bg-yellow-600 text-white';
      case 'alert':
        return 'bg-blue-600 text-white';
      default:
        return 'bg-gray-600 text-white';
    }
  };

  const getActionText = (action: string) => {
    switch (action) {
      case 'abort':
        return '中止';
      case 'freeze':
        return '凍結';
      case 'slow':
        return '減速';
      case 'alert':
        return 'アラート';
      default:
        return action;
    }
  };

  const getCategoryStats = () => {
    const stats: { [key: string]: { total: number; violated: number } } = {};

    OBSERVABILITY_CATEGORIES.forEach((cat) => {
      const categoryMetrics = metrics.filter((m) => m.category === cat.key);
      stats[cat.key] = {
        total: categoryMetrics.length,
        violated: categoryMetrics.filter((m) => m.violated).length,
      };
    });

    return stats;
  };

  const categoryStats = getCategoryStats();

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
            <h2 className="text-3xl font-bold tracking-tight">監視ダッシュボード</h2>
            <p className="text-muted-foreground">16分類観測メトリクスとアラート</p>
          </div>
          <div className="flex items-center space-x-3">
            <label className="flex items-center space-x-2 text-sm">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="w-4 h-4"
              />
              <span>自動更新（10秒）</span>
            </label>
            <button
              onClick={fetchData}
              className="px-4 py-2 text-sm border rounded-md hover:bg-accent"
            >
              🔄 更新
            </button>
            <a
              href="/"
              className="px-4 py-2 text-sm border rounded-md hover:bg-accent"
            >
              ← ダッシュボードに戻る
            </a>
          </div>
        </div>

        {/* サマリーカード */}
        <div className="grid gap-4 md:grid-cols-4 mb-8">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">アクティブ実行</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{activeRuns.length}</div>
              <p className="text-xs text-muted-foreground">現在実行中</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">総観測数</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{metrics.length}</div>
              <p className="text-xs text-muted-foreground">記録済みメトリクス</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">違反検知</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-yellow-600">{violationCount}</div>
              <p className="text-xs text-muted-foreground">しきい値超過</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">重大違反</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">{criticalCount}</div>
              <p className="text-xs text-muted-foreground">中止アクション</p>
            </CardContent>
          </Card>
        </div>

        {/* 16分類カテゴリ概要 */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>16分類観測カテゴリ</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
              <button
                onClick={() => setSelectedCategory('all')}
                className={`p-3 text-sm border rounded-lg transition-colors ${
                  selectedCategory === 'all'
                    ? 'border-primary bg-accent'
                    : 'border-border hover:border-primary/50'
                }`}
              >
                <div className="font-semibold">すべて</div>
                <div className="text-xs text-muted-foreground mt-1">
                  {metrics.length}件
                </div>
              </button>

              {OBSERVABILITY_CATEGORIES.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.key)}
                  className={`p-3 text-sm border rounded-lg transition-colors ${
                    selectedCategory === cat.key
                      ? 'border-primary bg-accent'
                      : 'border-border hover:border-primary/50'
                  }`}
                >
                  <div className="font-semibold">{cat.name}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {categoryStats[cat.key]?.violated || 0} / {categoryStats[cat.key]?.total || 0}
                  </div>
                  {categoryStats[cat.key]?.violated > 0 && (
                    <div className="text-xs text-red-600 mt-1">⚠ 違反あり</div>
                  )}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* アクティブ実行 & Kill Switch */}
        {activeRuns.length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>アクティブ実行 & Kill Switch</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {activeRuns.map((run) => (
                  <div
                    key={run.id}
                    className="flex items-center justify-between p-4 border rounded-lg"
                  >
                    <div>
                      <div className="font-semibold">
                        Run #{run.id} - {run.platform.toUpperCase()}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        開始: {new Date(run.started_at).toLocaleString('ja-JP')}
                      </div>
                    </div>
                    <button
                      onClick={() => handleKillSwitch(run.id)}
                      className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 font-semibold"
                    >
                      🛑 Kill Switch
                    </button>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* メトリクス一覧 */}
        <Card>
          <CardHeader>
            <CardTitle>
              観測メトリクス
              {selectedCategory !== 'all' && (
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  （{OBSERVABILITY_CATEGORIES.find((c) => c.key === selectedCategory)?.name}）
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="py-12 text-center text-muted-foreground">読み込み中...</div>
            ) : filteredMetrics.length === 0 ? (
              <div className="py-12 text-center text-muted-foreground">
                メトリクスはまだありません
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-3">Run ID</th>
                      <th className="text-left p-3">カテゴリ</th>
                      <th className="text-left p-3">メトリクス</th>
                      <th className="text-right p-3">実測値</th>
                      <th className="text-right p-3">しきい値</th>
                      <th className="text-center p-3">違反</th>
                      <th className="text-center p-3">アクション</th>
                      <th className="text-right p-3">記録日時</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredMetrics.map((metric) => (
                      <tr key={metric.id} className="border-b hover:bg-accent/50">
                        <td className="p-3">
                          <a
                            href={`/runs/${metric.run_id}`}
                            className="text-blue-600 hover:underline"
                          >
                            #{metric.run_id}
                          </a>
                        </td>
                        <td className="p-3">
                          {
                            OBSERVABILITY_CATEGORIES.find((c) => c.key === metric.category)
                              ?.name
                          }
                        </td>
                        <td className="p-3 font-mono text-xs">{metric.metric_key}</td>
                        <td className="p-3 text-right font-semibold">
                          {metric.metric_value.toFixed(2)}
                        </td>
                        <td className="p-3 text-right text-muted-foreground">
                          {metric.threshold_value.toFixed(2)}
                        </td>
                        <td className="p-3 text-center">
                          {metric.violated ? (
                            <span className="text-red-600 font-bold">⚠</span>
                          ) : (
                            <span className="text-green-600">✓</span>
                          )}
                        </td>
                        <td className="p-3 text-center">
                          <span
                            className={`px-2 py-1 text-xs rounded ${getActionColor(
                              metric.action_taken
                            )}`}
                          >
                            {getActionText(metric.action_taken)}
                          </span>
                        </td>
                        <td className="p-3 text-right text-xs text-muted-foreground">
                          {new Date(metric.timestamp).toLocaleString('ja-JP')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
