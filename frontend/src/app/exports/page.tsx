'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function ExportsPage() {
  const [exportType, setExportType] = useState<'csv' | 'json'>('csv');
  const [dataType, setDataType] = useState<'runs' | 'events' | 'metrics' | 'audits'>('runs');
  const [dateRange, setDateRange] = useState({
    start: '',
    end: '',
  });
  const [platform, setPlatform] = useState<string>('all');
  const [loading, setLoading] = useState(false);

  const handleExport = async () => {
    if (!dateRange.start || !dateRange.end) {
      alert('開始日時と終了日時を指定してください');
      return;
    }

    setLoading(true);

    try {
      // クエリパラメータを構築
      const params = new URLSearchParams({
        type: exportType,
        data_type: dataType,
        start_date: dateRange.start,
        end_date: dateRange.end,
      });

      if (platform !== 'all') {
        params.append('platform', platform);
      }

      const response = await fetch(`http://localhost:8006/exports?${params.toString()}`);

      if (!response.ok) {
        throw new Error('エクスポートに失敗しました');
      }

      // ファイルをダウンロード
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `export_${dataType}_${Date.now()}.${exportType}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      alert('エクスポートが完了しました');
    } catch (error) {
      console.error('Export failed:', error);
      alert('エラー: エクスポートに失敗しました');
    } finally {
      setLoading(false);
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
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">データエクスポート</h2>
            <p className="text-muted-foreground">CSV/JSON形式でデータを出力</p>
          </div>
          <a
            href="/"
            className="px-4 py-2 text-sm border rounded-md hover:bg-accent"
          >
            ← ダッシュボードに戻る
          </a>
        </div>

        <div className="max-w-2xl mx-auto">
          <Card>
            <CardHeader>
              <CardTitle>エクスポート設定</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* エクスポート形式 */}
              <div>
                <label className="block text-sm font-medium mb-3">エクスポート形式</label>
                <div className="grid grid-cols-2 gap-4">
                  <button
                    onClick={() => setExportType('csv')}
                    className={`p-4 border rounded-lg text-center transition-colors ${
                      exportType === 'csv'
                        ? 'border-primary bg-accent'
                        : 'border-border hover:border-primary/50'
                    }`}
                  >
                    <div className="font-semibold">CSV</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Excel等で開ける
                    </div>
                  </button>
                  <button
                    onClick={() => setExportType('json')}
                    className={`p-4 border rounded-lg text-center transition-colors ${
                      exportType === 'json'
                        ? 'border-primary bg-accent'
                        : 'border-border hover:border-primary/50'
                    }`}
                  >
                    <div className="font-semibold">JSON</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      プログラムで処理
                    </div>
                  </button>
                </div>
              </div>

              {/* データタイプ */}
              <div>
                <label className="block text-sm font-medium mb-3">データタイプ</label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => setDataType('runs')}
                    className={`p-3 border rounded-lg text-sm transition-colors ${
                      dataType === 'runs'
                        ? 'border-primary bg-accent'
                        : 'border-border hover:border-primary/50'
                    }`}
                  >
                    実行データ
                  </button>
                  <button
                    onClick={() => setDataType('events')}
                    className={`p-3 border rounded-lg text-sm transition-colors ${
                      dataType === 'events'
                        ? 'border-primary bg-accent'
                        : 'border-border hover:border-primary/50'
                    }`}
                  >
                    イベントログ
                  </button>
                  <button
                    onClick={() => setDataType('metrics')}
                    className={`p-3 border rounded-lg text-sm transition-colors ${
                      dataType === 'metrics'
                        ? 'border-primary bg-accent'
                        : 'border-border hover:border-primary/50'
                    }`}
                  >
                    監視メトリクス
                  </button>
                  <button
                    onClick={() => setDataType('audits')}
                    className={`p-3 border rounded-lg text-sm transition-colors ${
                      dataType === 'audits'
                        ? 'border-primary bg-accent'
                        : 'border-border hover:border-primary/50'
                    }`}
                  >
                    監査ログ
                  </button>
                </div>
              </div>

              {/* プラットフォーム */}
              <div>
                <label className="block text-sm font-medium mb-2">プラットフォーム</label>
                <select
                  value={platform}
                  onChange={(e) => setPlatform(e.target.value)}
                  className="w-full px-4 py-2 border rounded-md"
                >
                  <option value="all">すべて</option>
                  <option value="youtube">YouTube</option>
                  <option value="x">X (Twitter)</option>
                  <option value="instagram">Instagram</option>
                  <option value="tiktok">TikTok</option>
                </select>
              </div>

              {/* 期間 */}
              <div>
                <label className="block text-sm font-medium mb-3">期間</label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-muted-foreground mb-1">開始日時</label>
                    <input
                      type="datetime-local"
                      value={dateRange.start}
                      onChange={(e) => setDateRange({ ...dateRange, start: e.target.value })}
                      className="w-full px-4 py-2 border rounded-md"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-muted-foreground mb-1">終了日時</label>
                    <input
                      type="datetime-local"
                      value={dateRange.end}
                      onChange={(e) => setDateRange({ ...dateRange, end: e.target.value })}
                      className="w-full px-4 py-2 border rounded-md"
                    />
                  </div>
                </div>
                <div className="mt-2 flex space-x-2">
                  <button
                    onClick={() => {
                      const now = new Date();
                      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                      setDateRange({
                        start: today.toISOString().slice(0, 16),
                        end: now.toISOString().slice(0, 16),
                      });
                    }}
                    className="px-3 py-1 text-xs border rounded hover:bg-accent"
                  >
                    今日
                  </button>
                  <button
                    onClick={() => {
                      const now = new Date();
                      const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                      setDateRange({
                        start: weekAgo.toISOString().slice(0, 16),
                        end: now.toISOString().slice(0, 16),
                      });
                    }}
                    className="px-3 py-1 text-xs border rounded hover:bg-accent"
                  >
                    過去7日間
                  </button>
                  <button
                    onClick={() => {
                      const now = new Date();
                      const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
                      setDateRange({
                        start: monthAgo.toISOString().slice(0, 16),
                        end: now.toISOString().slice(0, 16),
                      });
                    }}
                    className="px-3 py-1 text-xs border rounded hover:bg-accent"
                  >
                    過去30日間
                  </button>
                </div>
              </div>

              {/* エクスポートボタン */}
              <button
                onClick={handleExport}
                disabled={loading || !dateRange.start || !dateRange.end}
                className="w-full px-6 py-3 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed font-semibold"
              >
                {loading ? 'エクスポート中...' : 'エクスポート'}
              </button>
            </CardContent>
          </Card>

          {/* 説明 */}
          <Card className="mt-6">
            <CardHeader>
              <CardTitle>エクスポートについて</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div>
                <h4 className="font-semibold mb-1">CSV形式</h4>
                <p className="text-muted-foreground">
                  Excelやスプレッドシートで開くことができます。
                  レポート作成や簡易分析に適しています。
                </p>
              </div>
              <div>
                <h4 className="font-semibold mb-1">JSON形式</h4>
                <p className="text-muted-foreground">
                  プログラムでの処理や他システムへのデータ連携に適しています。
                  完全な構造を保持したままエクスポートされます。
                </p>
              </div>
              <div>
                <h4 className="font-semibold mb-1">データタイプ</h4>
                <ul className="list-disc list-inside text-muted-foreground space-y-1">
                  <li>実行データ: 実行の設定や状態</li>
                  <li>イベントログ: 各実行のアクション履歴</li>
                  <li>監視メトリクス: 16分類観測データと違反情報</li>
                  <li>監査ログ: WORM形式の不可逆ログ</li>
                </ul>
              </div>
              <div>
                <h4 className="font-semibold mb-1">大量データの注意点</h4>
                <p className="text-muted-foreground">
                  長期間のデータをエクスポートする場合、ファイルサイズが大きくなることがあります。
                  必要な期間のみを指定することを推奨します。
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
