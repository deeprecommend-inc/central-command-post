'use client';

import { useEffect, useState, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface TaskLog {
  id: number;
  level: 'debug' | 'info' | 'warning' | 'error' | 'success';
  message: string;
  details: any;
  account_index: number | null;
  account_username: string | null;
  created_at: string;
}

interface TaskProgress {
  task_id: number;
  status: string;
  completed_count: number;
  failed_count: number;
  target_count: number;
  progress_percentage: number;
  current_batch: number;
  total_batches: number;
  started_at: string | null;
  latest_log: TaskLog | null;
}

interface TaskLogsProps {
  taskId: number;
}

const LOG_LEVEL_COLORS = {
  debug: 'text-gray-500',
  info: 'text-blue-600',
  warning: 'text-yellow-600',
  error: 'text-red-600',
  success: 'text-green-600',
};

const LOG_LEVEL_BG = {
  debug: 'bg-gray-100',
  info: 'bg-blue-50',
  warning: 'bg-yellow-50',
  error: 'bg-red-50',
  success: 'bg-green-50',
};

export default function TaskLogs({ taskId }: TaskLogsProps) {
  const [logs, setLogs] = useState<TaskLog[]>([]);
  const [progress, setProgress] = useState<TaskProgress | null>(null);
  const [lastLogId, setLastLogId] = useState<number>(0);
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // リアルタイムでログを取得（ポーリング）
  useEffect(() => {
    let isMounted = true;

    const fetchLogs = async () => {
      try {
        console.log(`[TaskLogs] Fetching logs for task ${taskId}, since=${lastLogId}`);
        const response = await fetch(
          `/api/account-generation/tasks/${taskId}/logs?since=${lastLogId}`
        );
        if (response.ok && isMounted) {
          const data = await response.json();
          console.log(`[TaskLogs] Received ${data.logs?.length || 0} new logs`);
          if (data.logs && data.logs.length > 0) {
            setLogs((prev) => [...prev, ...data.logs]);
            setLastLogId(data.logs[data.logs.length - 1].id);
          }
        }
      } catch (error) {
        console.error('[TaskLogs] Failed to fetch logs:', error);
      }
    };

    const fetchProgress = async () => {
      try {
        const response = await fetch(`/api/account-generation/tasks/${taskId}/progress`);
        if (response.ok && isMounted) {
          const data = await response.json();
          setProgress(data);
        }
      } catch (error) {
        console.error('[TaskLogs] Failed to fetch progress:', error);
      }
    };

    // 初回取得
    fetchLogs();
    fetchProgress();

    // ポーリング（1秒ごと）
    const logInterval = setInterval(fetchLogs, 1000);
    const progressInterval = setInterval(fetchProgress, 1000);

    return () => {
      isMounted = false;
      clearInterval(logInterval);
      clearInterval(progressInterval);
    };
  }, [taskId, lastLogId]);

  // 自動スクロール
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('ja-JP', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div className="space-y-4">
      {/* 進捗バー */}
      {progress && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">実行状況</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span>進捗: {progress.progress_percentage}%</span>
                <span>
                  {progress.completed_count + progress.failed_count} / {progress.target_count} 件
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
                <div className="flex h-full">
                  <div
                    className="bg-green-500 transition-all duration-300"
                    style={{
                      width: `${(progress.completed_count / progress.target_count) * 100}%`,
                    }}
                  />
                  <div
                    className="bg-red-500 transition-all duration-300"
                    style={{
                      width: `${(progress.failed_count / progress.target_count) * 100}%`,
                    }}
                  />
                </div>
              </div>
              <div className="flex justify-between text-xs text-muted-foreground mt-2">
                <span className="text-green-600">成功: {progress.completed_count}</span>
                <span className="text-red-600">失敗: {progress.failed_count}</span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <div className="text-muted-foreground">ステータス</div>
                <div className="font-medium capitalize">{progress.status}</div>
              </div>
              <div>
                <div className="text-muted-foreground">バッチ</div>
                <div className="font-medium">
                  {progress.current_batch} / {progress.total_batches}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">開始時刻</div>
                <div className="font-medium">
                  {progress.started_at
                    ? new Date(progress.started_at).toLocaleTimeString('ja-JP')
                    : '-'}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ログ表示 */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-lg">実行ログ</CardTitle>
          <label className="flex items-center space-x-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="rounded"
            />
            <span>自動スクロール</span>
          </label>
        </CardHeader>
        <CardContent>
          <div className="bg-black text-white rounded-lg p-4 h-96 overflow-y-auto font-mono text-sm">
            {logs.length === 0 ? (
              <div className="text-gray-500">ログはまだありません...</div>
            ) : (
              <>
                {logs.map((log) => (
                  <div
                    key={log.id}
                    className={`py-1 px-2 mb-1 rounded ${LOG_LEVEL_BG[log.level]} ${
                      LOG_LEVEL_COLORS[log.level]
                    }`}
                  >
                    <span className="text-gray-400">[{formatTime(log.created_at)}]</span>
                    <span className="ml-2 font-bold uppercase">[{log.level}]</span>
                    {log.account_index && (
                      <span className="ml-2 text-purple-600">[#{log.account_index}]</span>
                    )}
                    {log.account_username && (
                      <span className="ml-1 text-blue-600">@{log.account_username}</span>
                    )}
                    <span className="ml-2">{log.message}</span>
                  </div>
                ))}
                <div ref={logsEndRef} />
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
