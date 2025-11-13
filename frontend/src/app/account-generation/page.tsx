'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import TaskLogs from '@/components/TaskLogs';

interface GenerationTask {
  id: number;
  platform: string;
  target_count: number;
  completed_count: number;
  failed_count: number;
  status: string;
  generation_config: {
    username_pattern: string;
    email_domain: string;
    phone_provider: string | null;
  };
  proxy_list: string[];
  use_residential_proxy: boolean;
  headless: boolean;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

interface GeneratedAccount {
  id: number;
  task_id: number;
  platform: string;
  username: string;
  email: string;
  phone: string | null;
  proxy_used: string | null;
  verification_status: string;
  status: string;
  created_at: string;
  verified_at: string | null;
}

const PLATFORMS = [
  { id: 'youtube', name: 'YouTube', logo: '/youtube.png' },
  { id: 'x', name: 'X (Twitter)', logo: '/x.png' },
  { id: 'instagram', name: 'Instagram', logo: '/instagram.png' },
  { id: 'tiktok', name: 'TikTok', logo: '/tiktok.png' },
];

export default function AccountGenerationPage() {
  const [tasks, setTasks] = useState<GenerationTask[]>([]);
  const [accounts, setAccounts] = useState<GeneratedAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [selectedTaskForLogs, setSelectedTaskForLogs] = useState<number | null>(null);

  // フォーム状態
  const [formData, setFormData] = useState({
    platform: 'youtube',
    target_count: 10,
    username_pattern: 'user_{}',
    email_domain: 'temp-mail.com',
    phone_provider: '',
    proxy_list: '',
    use_residential_proxy: true,
    headless: true,
  });

  useEffect(() => {
    fetchTasks();
    fetchAccounts();
  }, []);

  const fetchTasks = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8006/account-generation/tasks');
      const data = await response.json();
      setTasks(data.tasks || []);
    } catch (error) {
      console.error('Failed to fetch tasks:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchAccounts = async () => {
    try {
      const response = await fetch('http://localhost:8006/account-generation/accounts');
      const data = await response.json();
      setAccounts(data.accounts || []);
    } catch (error) {
      console.error('Failed to fetch accounts:', error);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();

    const taskData = {
      platform: formData.platform,
      target_count: formData.target_count,
      username_pattern: formData.username_pattern,
      email_domain: formData.email_domain,
      phone_provider: formData.phone_provider || null,
      proxy_list: formData.proxy_list
        .split('\n')
        .map((p) => p.trim())
        .filter((p) => p.length > 0),
      use_residential_proxy: formData.use_residential_proxy,
      headless: formData.headless,
    };

    try {
      const response = await fetch('http://localhost:8006/account-generation/tasks', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(taskData),
      });

      const data = await response.json();

      if (data.success) {
        alert('アカウント生成タスクを作成しました！');
        setShowCreateForm(false);
        setFormData({
          platform: 'youtube',
          target_count: 10,
          username_pattern: 'user_{}',
          email_domain: 'temp-mail.com',
          phone_provider: '',
          proxy_list: '',
          use_residential_proxy: true,
          headless: true,
        });
        fetchTasks();
      } else {
        alert('エラー: ' + (data.error || 'タスクの作成に失敗しました'));
      }
    } catch (error) {
      console.error('Failed to create task:', error);
      alert('エラー: タスクの作成に失敗しました');
    }
  };

  const handleStart = async (taskId: number) => {
    try {
      const response = await fetch(
        `http://localhost:8006/account-generation/tasks/${taskId}/start`,
        {
          method: 'POST',
        }
      );

      const data = await response.json();

      if (data.success) {
        alert('タスクを開始しました');
        fetchTasks();
      } else {
        alert('エラー: ' + (data.error || 'タスクの開始に失敗しました'));
      }
    } catch (error) {
      console.error('Failed to start task:', error);
      alert('エラー: タスクの開始に失敗しました');
    }
  };

  const handleCancel = async (taskId: number) => {
    if (!confirm('このタスクをキャンセルしますか？')) {
      return;
    }

    try {
      const response = await fetch(
        `http://localhost:8006/account-generation/tasks/${taskId}/cancel`,
        {
          method: 'POST',
        }
      );

      const data = await response.json();

      if (data.success) {
        alert('タスクをキャンセルしました');
        fetchTasks();
      } else {
        alert('エラー: ' + (data.error || 'タスクのキャンセルに失敗しました'));
      }
    } catch (error) {
      console.error('Failed to cancel task:', error);
      alert('エラー: タスクのキャンセルに失敗しました');
    }
  };

  const handleDelete = async (taskId: number) => {
    if (!confirm('このタスクと生成されたアカウントを削除しますか？')) {
      return;
    }

    try {
      const response = await fetch(
        `http://localhost:8006/account-generation/tasks/${taskId}`,
        {
          method: 'DELETE',
        }
      );

      const data = await response.json();

      if (data.success) {
        alert('タスクを削除しました');
        fetchTasks();
        fetchAccounts();
      } else {
        alert('エラー: ' + (data.error || '削除に失敗しました'));
      }
    } catch (error) {
      console.error('Failed to delete task:', error);
      alert('エラー: 削除に失敗しました');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
        return 'bg-gray-100 text-gray-800';
      case 'generating':
        return 'bg-blue-100 text-blue-800';
      case 'verification':
        return 'bg-yellow-100 text-yellow-800';
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      case 'suspended':
        return 'bg-orange-100 text-orange-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'pending':
        return '待機中';
      case 'generating':
        return '生成中';
      case 'verification':
        return '認証待ち';
      case 'completed':
        return '完了';
      case 'failed':
        return '失敗';
      case 'suspended':
        return '停止';
      default:
        return status;
    }
  };

  const getPlatformInfo = (platformId: string) => {
    return PLATFORMS.find((p) => p.id === platformId) || { name: platformId, logo: '/default.png' };
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
            <h2 className="text-3xl font-bold tracking-tight">アカウント自動生成</h2>
            <p className="text-muted-foreground">SNSアカウントの一括生成と管理</p>
          </div>
          <div className="flex space-x-3">
            <a href="/" className="px-4 py-2 text-sm border rounded-md hover:bg-accent">
              ← ダッシュボードに戻る
            </a>
            <button
              onClick={() => setShowCreateForm(true)}
              className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              + 新規生成タスク
            </button>
          </div>
        </div>

        {/* タスク一覧とログ表示（2カラム） */}
        <div className="mb-8">
          <h3 className="text-xl font-semibold mb-4">生成タスク一覧</h3>
          {tasks.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center text-muted-foreground">
                タスクはまだありません
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* 左側：タスクカード */}
              <div className="space-y-4">
                {tasks.map((task) => {
                const platformInfo = getPlatformInfo(task.platform);
                return (
                  <Card key={task.id}>
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          <div className="w-10 h-10 relative flex-shrink-0">
                            <Image
                              src={platformInfo.logo}
                              alt={platformInfo.name}
                              fill
                              className="object-contain"
                            />
                          </div>
                          <div>
                            <CardTitle>
                              {platformInfo.name} - Task #{task.id}
                            </CardTitle>
                            <p className="text-sm text-muted-foreground mt-1">
                              目標: {task.target_count}件 / 完了: {task.completed_count}件 / 失敗:{' '}
                              {task.failed_count}件
                            </p>
                          </div>
                          <span className={`text-xs px-2 py-1 rounded ${getStatusColor(task.status)}`}>
                            {getStatusText(task.status)}
                          </span>
                        </div>
                        <div className="flex space-x-2">
                          {task.status === 'pending' && (
                            <button
                              onClick={() => handleStart(task.id)}
                              className="px-3 py-1 text-sm bg-green-600 text-white rounded-md hover:bg-green-700"
                            >
                              開始
                            </button>
                          )}
                          {task.status === 'generating' && (
                            <button
                              onClick={() => handleCancel(task.id)}
                              className="px-3 py-1 text-sm bg-yellow-600 text-white rounded-md hover:bg-yellow-700"
                            >
                              停止
                            </button>
                          )}
                          <button
                            onClick={() => setSelectedTaskForLogs(task.id)}
                            className={`px-3 py-1 text-sm border rounded-md ${
                              selectedTaskForLogs === task.id
                                ? 'bg-blue-600 text-white border-blue-600'
                                : 'border-blue-600 text-blue-600 hover:bg-blue-50'
                            }`}
                          >
                            {selectedTaskForLogs === task.id ? '✓ ログ表示中' : 'ログを表示'}
                          </button>
                          <button
                            onClick={() => handleDelete(task.id)}
                            className="px-3 py-1 text-sm border border-red-600 text-red-600 rounded-md hover:bg-red-50"
                          >
                            削除
                          </button>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                        <div>
                          <h4 className="font-semibold mb-1">生成設定</h4>
                          <div className="space-y-1 text-muted-foreground">
                            <div>ユーザー名パターン: {task.generation_config.username_pattern}</div>
                            <div>メールドメイン: {task.generation_config.email_domain}</div>
                            {task.generation_config.phone_provider && (
                              <div>電話番号プロバイダ: {task.generation_config.phone_provider}</div>
                            )}
                          </div>
                        </div>
                        <div>
                          <h4 className="font-semibold mb-1">実行設定</h4>
                          <div className="space-y-1 text-muted-foreground">
                            <div>プロキシ: {task.proxy_list.length > 0 ? `${task.proxy_list.length}件` : 'デフォルト'}</div>
                            <div>レジデンシャルプロキシ: {task.use_residential_proxy ? '有効' : '無効'}</div>
                            <div>ヘッドレスモード: {task.headless ? '有効' : '無効'}</div>
                          </div>
                        </div>
                        {task.error_message && (
                          <div className="md:col-span-2">
                            <h4 className="font-semibold mb-1 text-red-600">エラー</h4>
                            <div className="text-sm text-red-600">{task.error_message}</div>
                          </div>
                        )}
                        <div className="md:col-span-2">
                          <h4 className="font-semibold mb-1">タイムスタンプ</h4>
                          <div className="space-y-1 text-xs text-muted-foreground">
                            <div>作成: {new Date(task.created_at).toLocaleString('ja-JP')}</div>
                            {task.started_at && (
                              <div>開始: {new Date(task.started_at).toLocaleString('ja-JP')}</div>
                            )}
                            {task.completed_at && (
                              <div>完了: {new Date(task.completed_at).toLocaleString('ja-JP')}</div>
                            )}
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
              </div>

              {/* 右側：リアルタイムログ表示 */}
              <div className="lg:sticky lg:top-4 lg:self-start">
                {selectedTaskForLogs ? (
                  <div>
                    <div className="mb-4 flex items-center justify-between">
                      <h3 className="text-xl font-semibold">
                        タスク #{selectedTaskForLogs} - リアルタイムログ
                      </h3>
                      <button
                        onClick={() => setSelectedTaskForLogs(null)}
                        className="text-sm text-gray-500 hover:text-gray-700"
                      >
                        閉じる
                      </button>
                    </div>
                    <TaskLogs taskId={selectedTaskForLogs} />
                  </div>
                ) : (
                  <Card>
                    <CardContent className="py-12 text-center text-muted-foreground">
                      タスクを選択してログを表示
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          )}
        </div>

        {/* 生成されたアカウント一覧 */}
        <div className="mb-8">
          <h3 className="text-xl font-semibold mb-4">生成されたアカウント</h3>
          {accounts.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center text-muted-foreground">
                生成されたアカウントはまだありません
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="border-b bg-muted/50">
                      <tr>
                        <th className="px-4 py-3 text-left">ID</th>
                        <th className="px-4 py-3 text-left">プラットフォーム</th>
                        <th className="px-4 py-3 text-left">ユーザー名</th>
                        <th className="px-4 py-3 text-left">メール</th>
                        <th className="px-4 py-3 text-left">認証状態</th>
                        <th className="px-4 py-3 text-left">ステータス</th>
                        <th className="px-4 py-3 text-left">作成日時</th>
                      </tr>
                    </thead>
                    <tbody>
                      {accounts.map((account) => {
                        const platformInfo = getPlatformInfo(account.platform);
                        return (
                          <tr key={account.id} className="border-b hover:bg-muted/30">
                            <td className="px-4 py-3">{account.id}</td>
                            <td className="px-4 py-3">
                              <span className="flex items-center space-x-2">
                                <div className="w-6 h-6 relative flex-shrink-0">
                                  <Image
                                    src={platformInfo.logo}
                                    alt={platformInfo.name}
                                    fill
                                    className="object-contain"
                                  />
                                </div>
                                <span>{platformInfo.name}</span>
                              </span>
                            </td>
                            <td className="px-4 py-3 font-mono">{account.username}</td>
                            <td className="px-4 py-3 font-mono text-xs">{account.email}</td>
                            <td className="px-4 py-3">
                              <span
                                className={`text-xs px-2 py-1 rounded ${
                                  account.verification_status === 'verified'
                                    ? 'bg-green-100 text-green-800'
                                    : account.verification_status === 'failed'
                                    ? 'bg-red-100 text-red-800'
                                    : 'bg-yellow-100 text-yellow-800'
                                }`}
                              >
                                {account.verification_status === 'verified'
                                  ? '認証済み'
                                  : account.verification_status === 'failed'
                                  ? '失敗'
                                  : '待機中'}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <span className={`text-xs px-2 py-1 rounded ${getStatusColor(account.status)}`}>
                                {account.status === 'active' ? '有効' : account.status}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-xs">
                              {new Date(account.created_at).toLocaleString('ja-JP')}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* 新規作成フォーム */}
        {showCreateForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
            <Card className="max-w-2xl w-full max-h-[90vh] overflow-y-auto">
              <CardHeader>
                <CardTitle>新規アカウント生成タスク作成</CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleCreate} className="space-y-4">
                  {/* プラットフォーム選択 */}
                  <div>
                    <label className="block text-sm font-medium mb-2">プラットフォーム</label>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      {PLATFORMS.map((platform) => (
                        <button
                          key={platform.id}
                          type="button"
                          onClick={() => setFormData({ ...formData, platform: platform.id })}
                          className={`p-4 border rounded-lg text-center transition-colors ${
                            formData.platform === platform.id
                              ? 'border-primary bg-accent'
                              : 'border-border hover:border-primary/50'
                          }`}
                        >
                          <div className="w-12 h-12 relative mx-auto mb-2">
                            <Image
                              src={platform.logo}
                              alt={platform.name}
                              fill
                              className="object-contain"
                            />
                          </div>
                          <div className="text-sm">{platform.name}</div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* 生成数 */}
                  <div>
                    <label className="block text-sm font-medium mb-2">生成数</label>
                    <input
                      type="number"
                      value={formData.target_count}
                      onChange={(e) =>
                        setFormData({ ...formData, target_count: parseInt(e.target.value) })
                      }
                      className="w-full px-4 py-2 border rounded-md"
                      min="1"
                      max="100"
                      required
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      生成するアカウント数（1〜100件）
                    </p>
                  </div>

                  {/* ユーザー名パターン */}
                  <div>
                    <label className="block text-sm font-medium mb-2">ユーザー名パターン</label>
                    <input
                      type="text"
                      value={formData.username_pattern}
                      onChange={(e) => setFormData({ ...formData, username_pattern: e.target.value })}
                      className="w-full px-4 py-2 border rounded-md"
                      placeholder="例: user_{}, test_{:04d}, random"
                      required
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      {}は連番に置き換えられます。randomでランダム生成
                    </p>
                  </div>

                  {/* メールドメイン */}
                  <div>
                    <label className="block text-sm font-medium mb-2">メールドメイン</label>
                    <input
                      type="text"
                      value={formData.email_domain}
                      onChange={(e) => setFormData({ ...formData, email_domain: e.target.value })}
                      className="w-full px-4 py-2 border rounded-md"
                      placeholder="例: temp-mail.com, guerrillamail.com"
                      required
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      一時メールサービスのドメインを推奨
                    </p>
                  </div>

                  {/* 電話番号プロバイダ */}
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      電話番号プロバイダ（オプション）
                    </label>
                    <input
                      type="text"
                      value={formData.phone_provider}
                      onChange={(e) => setFormData({ ...formData, phone_provider: e.target.value })}
                      className="w-full px-4 py-2 border rounded-md"
                      placeholder="例: sms-activate.org"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      SMS認証が必要な場合に使用
                    </p>
                  </div>

                  {/* プロキシリスト */}
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      プロキシリスト（1行に1つ）
                    </label>
                    <textarea
                      value={formData.proxy_list}
                      onChange={(e) => setFormData({ ...formData, proxy_list: e.target.value })}
                      placeholder={'例:\n123.45.67.89:8080\nproxy1.example.com:3128'}
                      className="w-full px-4 py-2 border rounded-md min-h-[100px] font-mono text-sm"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      空欄の場合はデフォルトIPを使用
                    </p>
                  </div>

                  {/* チェックボックス設定 */}
                  <div className="space-y-3">
                    <div className="border rounded-lg p-4 bg-accent/30">
                      <label className="flex items-start space-x-3 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={formData.use_residential_proxy}
                          onChange={(e) =>
                            setFormData({ ...formData, use_residential_proxy: e.target.checked })
                          }
                          className="w-4 h-4 mt-1"
                        />
                        <div className="flex-1">
                          <div className="font-medium text-sm">レジデンシャルプロキシを使用（推奨）</div>
                          <div className="text-xs text-muted-foreground mt-1">
                            一般家庭のIPアドレスを使用し、Bot検知を回避します
                          </div>
                        </div>
                      </label>
                    </div>

                    <div className="border rounded-lg p-4 bg-accent/30">
                      <label className="flex items-start space-x-3 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={formData.headless}
                          onChange={(e) => setFormData({ ...formData, headless: e.target.checked })}
                          className="w-4 h-4 mt-1"
                        />
                        <div className="flex-1">
                          <div className="font-medium text-sm">ヘッドレスモードで実行（推奨）</div>
                          <div className="text-xs text-muted-foreground mt-1">
                            ブラウザ画面を表示せず、バックグラウンドで実行します
                          </div>
                        </div>
                      </label>
                    </div>
                  </div>

                  {/* ボタン */}
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
                          platform: 'youtube',
                          target_count: 10,
                          username_pattern: 'user_{}',
                          email_domain: 'temp-mail.com',
                          phone_provider: '',
                          proxy_list: '',
                          use_residential_proxy: true,
                          headless: true,
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

        {/* 注意事項 */}
        <Card className="mt-8">
          <CardHeader>
            <CardTitle>⚠️ 重要事項</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <h4 className="font-semibold mb-1 text-red-600">利用規約の確認</h4>
              <p className="text-muted-foreground">
                各SNSプラットフォームの利用規約を必ず確認してください。
                自動アカウント生成が禁止されているプラットフォームもあります。
              </p>
            </div>
            <div>
              <h4 className="font-semibold mb-1 text-red-600">認可された用途のみ</h4>
              <p className="text-muted-foreground">
                この機能は、正当な業務目的（マーケティング、QAテスト等）のみで使用してください。
                スパム行為や不正利用は禁止されています。
              </p>
            </div>
            <div>
              <h4 className="font-semibold mb-1">レート制限</h4>
              <p className="text-muted-foreground">
                プラットフォームのレート制限を守るため、生成は自動的にペース配分されます。
                短時間に大量のアカウントを生成すると検知される可能性があります。
              </p>
            </div>
            <div>
              <h4 className="font-semibold mb-1">認証プロセス</h4>
              <p className="text-muted-foreground">
                多くのプラットフォームはSMS認証や画像認証を要求します。
                電話番号プロバイダの設定が必要になる場合があります。
              </p>
            </div>
            <div>
              <h4 className="font-semibold mb-1">データセキュリティ</h4>
              <p className="text-muted-foreground">
                生成されたアカウント情報（パスワード、トークン等）は暗号化して保存されます。
                不正アクセスを防ぐため、適切なアクセス制御を実施してください。
              </p>
            </div>
          </CardContent>
        </Card>
      </main>

      {/* ログモーダル */}
      {selectedTaskForLogs && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-5xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            <div className="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-center">
              <h2 className="text-xl font-bold">タスク #{selectedTaskForLogs} - 実行ログ</h2>
              <button
                onClick={() => setSelectedTaskForLogs(null)}
                className="text-gray-500 hover:text-gray-700 text-2xl"
              >
                ✕
              </button>
            </div>
            <div className="p-6 overflow-y-auto flex-1">
              <TaskLogs taskId={selectedTaskForLogs} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
