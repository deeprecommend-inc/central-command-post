'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface Account {
  id: number;
  username: string;
  platform: string;
  email?: string;
}

interface BrowserActionResult {
  success: boolean;
  result: string | null;
  actions_taken: string[];
  screenshots: string[];
  execution_time: number;
  error: string | null;
}

interface TaskExample {
  youtube: string[];
  x: string[];
  instagram: string[];
  tiktok: string[];
}

export default function BrowserActionsPage() {
  const [task, setTask] = useState('');
  const [platform, setPlatform] = useState('youtube');
  const [accountId, setAccountId] = useState<number | null>(null);
  const [useGeneratedAccount, setUseGeneratedAccount] = useState(false);
  const [headless, setHeadless] = useState(true);
  const [useCloud, setUseCloud] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BrowserActionResult | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [generatedAccounts, setGeneratedAccounts] = useState<Account[]>([]);
  const [examples, setExamples] = useState<TaskExample | null>(null);

  useEffect(() => {
    fetchAccounts();
    fetchExamples();
  }, []);

  const fetchAccounts = async () => {
    try {
      const [accountsRes, generatedRes] = await Promise.all([
        fetch('http://localhost:8006/accounts'),
        fetch('http://localhost:8006/generated-accounts'),
      ]);

      if (accountsRes.ok) {
        const data = await accountsRes.json();
        setAccounts(data.accounts || []);
      }

      if (generatedRes.ok) {
        const data = await generatedRes.json();
        setGeneratedAccounts(data.accounts || []);
      }
    } catch (error) {
      console.error('Failed to fetch accounts:', error);
    }
  };

  const fetchExamples = async () => {
    try {
      const response = await fetch('http://localhost:8006/browser-actions/examples');
      if (response.ok) {
        const data = await response.json();
        setExamples(data);
      }
    } catch (error) {
      console.error('Failed to fetch examples:', error);
    }
  };

  const executeAction = async () => {
    if (!task.trim()) {
      alert('タスクを入力してください');
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const response = await fetch('http://localhost:8006/browser-actions/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          task,
          platform,
          account_id: accountId,
          use_generated_account: useGeneratedAccount,
          browser_config: { headless },
          use_cloud: useCloud,
        }),
      });

      const data = await response.json();
      setResult(data);
    } catch (error) {
      setResult({
        success: false,
        result: null,
        actions_taken: [],
        screenshots: [],
        execution_time: 0,
        error: error instanceof Error ? error.message : 'Unknown error',
      });
    } finally {
      setLoading(false);
    }
  };

  const currentAccounts = useGeneratedAccount ? generatedAccounts : accounts;
  const filteredAccounts = currentAccounts.filter(
    (acc) => acc.platform.toLowerCase() === platform.toLowerCase()
  );

  const platformExamples = examples ? examples[platform as keyof TaskExample] || [] : [];

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold">ブラウザアクション</h1>
          <p className="text-sm text-muted-foreground">
            AIブラウザ自動化 - 自然言語でSNS操作
          </p>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="grid gap-6 md:grid-cols-2">
          {/* Task Input */}
          <Card>
            <CardHeader>
              <CardTitle>タスク設定</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Platform Selection */}
              <div>
                <label className="block text-sm font-medium mb-2">
                  プラットフォーム
                </label>
                <select
                  value={platform}
                  onChange={(e) => {
                    setPlatform(e.target.value);
                    setAccountId(null);
                  }}
                  className="w-full px-3 py-2 border rounded-md"
                >
                  <option value="youtube">YouTube</option>
                  <option value="x">X (Twitter)</option>
                  <option value="instagram">Instagram</option>
                  <option value="tiktok">TikTok</option>
                </select>
              </div>

              {/* Account Type */}
              <div>
                <label className="block text-sm font-medium mb-2">
                  アカウントタイプ
                </label>
                <div className="flex gap-4">
                  <label className="flex items-center">
                    <input
                      type="radio"
                      checked={!useGeneratedAccount}
                      onChange={() => {
                        setUseGeneratedAccount(false);
                        setAccountId(null);
                      }}
                      className="mr-2"
                    />
                    既存アカウント
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      checked={useGeneratedAccount}
                      onChange={() => {
                        setUseGeneratedAccount(true);
                        setAccountId(null);
                      }}
                      className="mr-2"
                    />
                    生成アカウント
                  </label>
                </div>
              </div>

              {/* Account Selection */}
              <div>
                <label className="block text-sm font-medium mb-2">
                  アカウント選択
                </label>
                <select
                  value={accountId || ''}
                  onChange={(e) => setAccountId(e.target.value ? Number(e.target.value) : null)}
                  className="w-full px-3 py-2 border rounded-md"
                >
                  <option value="">アカウントなし（ログインなし）</option>
                  {filteredAccounts.map((acc) => (
                    <option key={acc.id} value={acc.id}>
                      {acc.username} ({acc.email || 'no email'})
                    </option>
                  ))}
                </select>
                {filteredAccounts.length === 0 && (
                  <p className="text-xs text-muted-foreground mt-1">
                    このプラットフォームのアカウントがありません
                  </p>
                )}
              </div>

              {/* Task Input */}
              <div>
                <label className="block text-sm font-medium mb-2">
                  タスク（自然言語）
                </label>
                <textarea
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  placeholder="例: YouTube で「AI tutorial」を検索して、上位5つの動画にいいねする"
                  className="w-full px-3 py-2 border rounded-md h-32 resize-none"
                />
              </div>

              {/* Options */}
              <div className="flex gap-4">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={headless}
                    onChange={(e) => setHeadless(e.target.checked)}
                    className="mr-2"
                  />
                  ヘッドレスモード
                </label>
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={useCloud}
                    onChange={(e) => setUseCloud(e.target.checked)}
                    className="mr-2"
                  />
                  クラウドモード
                </label>
              </div>

              {/* Execute Button */}
              <button
                onClick={executeAction}
                disabled={loading}
                className="w-full px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
              >
                {loading ? '実行中...' : 'タスクを実行'}
              </button>
            </CardContent>
          </Card>

          {/* Examples */}
          <Card>
            <CardHeader>
              <CardTitle>タスク例 - {platform.toUpperCase()}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {platformExamples.map((example, index) => (
                  <button
                    key={index}
                    onClick={() => setTask(example)}
                    className="w-full text-left px-3 py-2 text-sm border rounded-md hover:bg-accent transition-colors"
                  >
                    {example}
                  </button>
                ))}
                {platformExamples.length === 0 && (
                  <p className="text-muted-foreground text-sm">
                    例を読み込み中...
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Result */}
        {result && (
          <Card className="mt-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                実行結果
                <span
                  className={`px-2 py-1 text-xs rounded ${
                    result.success
                      ? 'bg-green-100 text-green-800'
                      : 'bg-red-100 text-red-800'
                  }`}
                >
                  {result.success ? '成功' : '失敗'}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Result Text */}
              <div>
                <h4 className="font-medium mb-1">結果</h4>
                <p className="text-sm bg-muted p-3 rounded">
                  {result.result || result.error || '結果なし'}
                </p>
              </div>

              {/* Execution Time */}
              <div>
                <h4 className="font-medium mb-1">実行時間</h4>
                <p className="text-sm">{result.execution_time.toFixed(2)} 秒</p>
              </div>

              {/* Actions Taken */}
              {result.actions_taken.length > 0 && (
                <div>
                  <h4 className="font-medium mb-1">実行アクション</h4>
                  <ul className="list-disc list-inside text-sm space-y-1">
                    {result.actions_taken.map((action, index) => (
                      <li key={index}>{action}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Error */}
              {result.error && (
                <div>
                  <h4 className="font-medium mb-1 text-destructive">エラー</h4>
                  <p className="text-sm bg-destructive/10 text-destructive p-3 rounded">
                    {result.error}
                  </p>
                </div>
              )}

              {/* Screenshots */}
              {result.screenshots.length > 0 && (
                <div>
                  <h4 className="font-medium mb-1">スクリーンショット</h4>
                  <div className="grid grid-cols-2 gap-2">
                    {result.screenshots.map((screenshot, index) => (
                      <img
                        key={index}
                        src={`data:image/png;base64,${screenshot}`}
                        alt={`Screenshot ${index + 1}`}
                        className="border rounded"
                      />
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Info Card */}
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>ブラウザアクションについて</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>
              <strong>ブラウザアクション</strong>は、browser-useライブラリを使用したAI駆動のブラウザ自動化機能です。
              自然言語でタスクを記述するだけで、AIがブラウザを操作してSNSアクションを実行します。
            </p>
            <p>
              <strong>特徴:</strong>
            </p>
            <ul className="list-disc list-inside space-y-1">
              <li>OAuth認証不要 - ブラウザログインで動作</li>
              <li>自然言語でタスク指定可能</li>
              <li>複数のSNSプラットフォームに対応</li>
              <li>スクリーンショットによる実行確認</li>
              <li>クラウドモードでステルス性向上</li>
            </ul>
            <p className="text-yellow-600">
              <strong>注意:</strong> レート制限やCAPTCHAに注意してください。
              過度な自動化はアカウント停止の原因になる可能性があります。
            </p>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
