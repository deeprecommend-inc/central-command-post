'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface Draft {
  id: number;
  run_id: number;
  platform: string;
  draft_type: string;
  outputs_json: {
    drafts?: string[];
    content?: string;
    reply_to?: string;
  };
  toxicity_score: number;
  duplication_rate: number;
  status: string;
  created_at: string;
}

export default function DraftsPage() {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDraft, setSelectedDraft] = useState<Draft | null>(null);
  const [editedContent, setEditedContent] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('pending');

  useEffect(() => {
    fetchDrafts();
  }, [filterStatus]);

  const fetchDrafts = async () => {
    try {
      setLoading(true);
      const response = await fetch(`http://localhost:8006/drafts/?status=${filterStatus}`);
      const data = await response.json();
      setDrafts(data.drafts || []);
    } catch (error) {
      console.error('Failed to fetch drafts:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (draftId: number) => {
    try {
      const response = await fetch(`http://localhost:8006/drafts/${draftId}/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (data.success) {
        alert('承認しました！');
        fetchDrafts();
        setSelectedDraft(null);
      } else {
        alert('エラー: ' + (data.error || '承認に失敗しました'));
      }
    } catch (error) {
      console.error('Failed to approve draft:', error);
      alert('エラー: 承認に失敗しました');
    }
  };

  const handleReject = async (draftId: number, reason: string) => {
    try {
      const response = await fetch(`http://localhost:8006/drafts/${draftId}/reject`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ reason }),
      });

      const data = await response.json();

      if (data.success) {
        alert('差戻ししました');
        fetchDrafts();
        setSelectedDraft(null);
      } else {
        alert('エラー: ' + (data.error || '差戻しに失敗しました'));
      }
    } catch (error) {
      console.error('Failed to reject draft:', error);
      alert('エラー: 差戻しに失敗しました');
    }
  };

  const handleEdit = async (draftId: number, newContent: string) => {
    try {
      const response = await fetch(`http://localhost:8006/drafts/${draftId}/edit`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content: newContent }),
      });

      const data = await response.json();

      if (data.success) {
        alert('編集を保存しました');
        fetchDrafts();
        setSelectedDraft(null);
        setEditedContent('');
      } else {
        alert('エラー: ' + (data.error || '編集に失敗しました'));
      }
    } catch (error) {
      console.error('Failed to edit draft:', error);
      alert('エラー: 編集に失敗しました');
    }
  };

  const openDraftDetail = (draft: Draft) => {
    setSelectedDraft(draft);
    setEditedContent(
      draft.outputs_json.drafts?.[0] || draft.outputs_json.content || ''
    );
  };

  const getToxicityColor = (score: number) => {
    if (score >= 0.7) return 'text-red-600';
    if (score >= 0.4) return 'text-yellow-600';
    return 'text-green-600';
  };

  const getDuplicationColor = (rate: number) => {
    if (rate >= 70) return 'text-red-600';
    if (rate >= 40) return 'text-yellow-600';
    return 'text-green-600';
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
            <h2 className="text-3xl font-bold tracking-tight">承認キュー</h2>
            <p className="text-muted-foreground">AI生成案のレビューと承認</p>
          </div>
          <a
            href="/"
            className="px-4 py-2 text-sm border rounded-md hover:bg-accent"
          >
            ← ダッシュボードに戻る
          </a>
        </div>

        {/* フィルタ */}
        <div className="mb-6">
          <div className="flex space-x-2">
            <button
              onClick={() => setFilterStatus('pending')}
              className={`px-4 py-2 text-sm rounded-md ${
                filterStatus === 'pending'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-accent hover:bg-accent/80'
              }`}
            >
              承認待ち
            </button>
            <button
              onClick={() => setFilterStatus('approved')}
              className={`px-4 py-2 text-sm rounded-md ${
                filterStatus === 'approved'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-accent hover:bg-accent/80'
              }`}
            >
              承認済み
            </button>
            <button
              onClick={() => setFilterStatus('rejected')}
              className={`px-4 py-2 text-sm rounded-md ${
                filterStatus === 'rejected'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-accent hover:bg-accent/80'
              }`}
            >
              差戻し
            </button>
          </div>
        </div>

        {/* Draft一覧 */}
        {drafts.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center text-muted-foreground">
              承認待ちの下書きはありません
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {drafts.map((draft) => (
              <Card key={draft.id} className="cursor-pointer hover:shadow-md">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">
                      {draft.platform.toUpperCase()} - {draft.draft_type}
                    </CardTitle>
                    <span
                      className={`text-xs px-2 py-1 rounded ${
                        draft.status === 'pending'
                          ? 'bg-yellow-100 text-yellow-800'
                          : draft.status === 'approved'
                          ? 'bg-green-100 text-green-800'
                          : 'bg-red-100 text-red-800'
                      }`}
                    >
                      {draft.status === 'pending'
                        ? '承認待ち'
                        : draft.status === 'approved'
                        ? '承認済み'
                        : '差戻し'}
                    </span>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="text-sm line-clamp-3">
                      {draft.outputs_json.drafts?.[0] ||
                        draft.outputs_json.content ||
                        '(内容なし)'}
                    </div>

                    <div className="flex items-center justify-between text-xs">
                      <div>
                        <span className="text-muted-foreground">有害性: </span>
                        <span
                          className={`font-semibold ${getToxicityColor(
                            draft.toxicity_score
                          )}`}
                        >
                          {(draft.toxicity_score * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">重複率: </span>
                        <span
                          className={`font-semibold ${getDuplicationColor(
                            draft.duplication_rate
                          )}`}
                        >
                          {draft.duplication_rate.toFixed(1)}%
                        </span>
                      </div>
                    </div>

                    <div className="text-xs text-muted-foreground">
                      Run ID: {draft.run_id} • {new Date(draft.created_at).toLocaleString('ja-JP')}
                    </div>

                    {draft.status === 'pending' && (
                      <button
                        onClick={() => openDraftDetail(draft)}
                        className="w-full px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
                      >
                        レビュー
                      </button>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Draft詳細モーダル */}
        {selectedDraft && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
            <Card className="max-w-2xl w-full max-h-[90vh] overflow-y-auto">
              <CardHeader>
                <CardTitle>
                  {selectedDraft.platform.toUpperCase()} - {selectedDraft.draft_type}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">コンテンツ</label>
                  <textarea
                    value={editedContent}
                    onChange={(e) => setEditedContent(e.target.value)}
                    className="w-full px-4 py-2 border rounded-md min-h-[200px]"
                  />
                </div>

                {selectedDraft.outputs_json.reply_to && (
                  <div>
                    <label className="block text-sm font-medium mb-2">返信先</label>
                    <div className="px-4 py-2 bg-accent rounded-md text-sm">
                      {selectedDraft.outputs_json.reply_to}
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">有害性スコア</label>
                    <div
                      className={`text-2xl font-bold ${getToxicityColor(
                        selectedDraft.toxicity_score
                      )}`}
                    >
                      {(selectedDraft.toxicity_score * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">重複率</label>
                    <div
                      className={`text-2xl font-bold ${getDuplicationColor(
                        selectedDraft.duplication_rate
                      )}`}
                    >
                      {selectedDraft.duplication_rate.toFixed(1)}%
                    </div>
                  </div>
                </div>

                {selectedDraft.outputs_json.drafts && selectedDraft.outputs_json.drafts.length > 1 && (
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      その他の候補 ({selectedDraft.outputs_json.drafts.length - 1}件)
                    </label>
                    <div className="space-y-2">
                      {selectedDraft.outputs_json.drafts.slice(1).map((draft, idx) => (
                        <div
                          key={idx}
                          className="px-3 py-2 bg-accent rounded text-sm cursor-pointer hover:bg-accent/80"
                          onClick={() => setEditedContent(draft)}
                        >
                          {draft}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex space-x-3 pt-4">
                  <button
                    onClick={() => handleApprove(selectedDraft.id)}
                    className="flex-1 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
                  >
                    承認して実行
                  </button>
                  <button
                    onClick={() => {
                      if (editedContent !== (selectedDraft.outputs_json.drafts?.[0] || selectedDraft.outputs_json.content || '')) {
                        handleEdit(selectedDraft.id, editedContent);
                      } else {
                        alert('内容を編集してください');
                      }
                    }}
                    className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                  >
                    編集して保存
                  </button>
                  <button
                    onClick={() => {
                      const reason = prompt('差戻し理由を入力してください');
                      if (reason) {
                        handleReject(selectedDraft.id, reason);
                      }
                    }}
                    className="flex-1 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
                  >
                    差戻し
                  </button>
                  <button
                    onClick={() => {
                      setSelectedDraft(null);
                      setEditedContent('');
                    }}
                    className="px-4 py-2 border rounded-md hover:bg-accent"
                  >
                    閉じる
                  </button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}
