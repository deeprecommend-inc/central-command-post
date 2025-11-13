"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import axios from "axios"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8006"

interface ProxyIP {
  id: number
  ip_address: string
  port: number
  proxy_type: string
  is_residential: boolean
  is_mobile: boolean
  country_code: string | null
  quality: string
  response_time_ms: number | null
  success_rate: number
  total_requests: number
  last_used_at: string | null
  last_tested_at: string | null
  is_active: boolean
  is_banned: boolean
  created_at: string
}

interface ProxyStats {
  total: number
  active: number
  residential: number
  quality_breakdown: {
    excellent: number
    good: number
    fair: number
    poor: number
    untested: number
  }
}

const QUALITY_COLORS = {
  excellent: "bg-green-100 text-green-800",
  good: "bg-blue-100 text-blue-800",
  fair: "bg-yellow-100 text-yellow-800",
  poor: "bg-red-100 text-red-800",
  untested: "bg-gray-100 text-gray-800"
}

const QUALITY_LABELS = {
  excellent: "優良",
  good: "良好",
  fair: "普通",
  poor: "低品質",
  untested: "未テスト"
}

export default function ProxyIPsPage() {
  const [proxies, setProxies] = useState<ProxyIP[]>([])
  const [stats, setStats] = useState<ProxyStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  // フィルター
  const [selectedQuality, setSelectedQuality] = useState<string>("all")
  const [showActiveOnly, setShowActiveOnly] = useState(true)
  const [showResidentialOnly, setShowResidentialOnly] = useState(false)

  // インポート
  const [importText, setImportText] = useState("")
  const [importDialogOpen, setImportDialogOpen] = useState(false)
  const [importLoading, setImportLoading] = useState(false)

  // IP抽出
  const [extractedIPs, setExtractedIPs] = useState<any[]>([])
  const [showExtractPreview, setShowExtractPreview] = useState(false)

  // テスト
  const [testingAll, setTestingAll] = useState(false)

  useEffect(() => {
    fetchProxies()
    fetchStats()
  }, [selectedQuality, showActiveOnly, showResidentialOnly])

  const fetchProxies = async () => {
    setLoading(true)
    setError("")

    try {
      const params: any = {}
      if (selectedQuality !== "all") {
        params.quality = selectedQuality
      }
      if (showActiveOnly) {
        params.is_active = true
      }
      if (showResidentialOnly) {
        params.is_residential = true
      }

      const response = await axios.get(`${API_URL}/proxy-ips/`, { params })
      setProxies(response.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to fetch proxies")
    } finally {
      setLoading(false)
    }
  }

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API_URL}/proxy-ips/stats`)
      setStats(response.data)
    } catch (err) {
      console.error("Failed to fetch stats:", err)
    }
  }

  const extractIPsFromText = (text: string) => {
    const lines = text.trim().split('\n')
    const extracted: any[] = []

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith('#')) continue

      const parsed = parseProxyLine(trimmed)
      if (parsed) {
        extracted.push(parsed)
      }
    }

    return extracted
  }

  const parseProxyLine = (line: string): any | null => {
    // プロトコル指定あり: http://IP:PORT, socks5://IP:PORT
    const protocolMatch = line.match(/^(https?|socks5):\/\/(.+)/)
    let proxyType = "http"
    let rest = line

    if (protocolMatch) {
      proxyType = protocolMatch[1] === "socks5" ? "socks5" : "http"
      rest = protocolMatch[2]
    }

    // USER:PASS@IP:PORT 形式
    const authMatch = rest.match(/^([^:]+):([^@]+)@([^:]+):(\d+)/)
    if (authMatch) {
      return {
        ip_address: authMatch[3],
        port: parseInt(authMatch[4]),
        username: authMatch[1],
        password: authMatch[2],
        proxy_type: proxyType,
        original: line
      }
    }

    // IP:PORT:USER:PASS 形式
    const fullMatch = rest.match(/^([^:]+):(\d+):([^:]+):(.+)/)
    if (fullMatch) {
      return {
        ip_address: fullMatch[1],
        port: parseInt(fullMatch[2]),
        username: fullMatch[3],
        password: fullMatch[4],
        proxy_type: proxyType,
        original: line
      }
    }

    // IP:PORT 形式
    const simpleMatch = rest.match(/^([^:]+):(\d+)/)
    if (simpleMatch) {
      return {
        ip_address: simpleMatch[1],
        port: parseInt(simpleMatch[2]),
        proxy_type: proxyType,
        original: line
      }
    }

    return null
  }

  const handleExtractIPs = () => {
    if (!importText.trim()) {
      alert("テキストを入力してください")
      return
    }

    const extracted = extractIPsFromText(importText)

    if (extracted.length === 0) {
      alert("有効なプロキシが見つかりませんでした")
      return
    }

    setExtractedIPs(extracted)
    setShowExtractPreview(true)
  }

  const handleRemoveExtracted = (index: number) => {
    setExtractedIPs(extractedIPs.filter((_, i) => i !== index))
  }

  const handleImportExtracted = async () => {
    if (extractedIPs.length === 0) {
      alert("インポートするプロキシがありません")
      return
    }

    setImportLoading(true)

    try {
      const response = await axios.post(`${API_URL}/proxy-ips/bulk-import`, {
        raw_text: extractedIPs.map(ip => ip.original).join('\n'),
        proxy_type: "http",
        is_residential: false,
        source: "manual_import"
      })

      alert(
        `インポート完了\n` +
        `追加: ${response.data.added}\n` +
        `スキップ: ${response.data.skipped_duplicates}\n` +
        `無効: ${response.data.invalid}`
      )

      setImportText("")
      setExtractedIPs([])
      setShowExtractPreview(false)
      setImportDialogOpen(false)
      fetchProxies()
      fetchStats()
    } catch (err: any) {
      alert(err.response?.data?.detail || "インポートに失敗しました")
    } finally {
      setImportLoading(false)
    }
  }

  const handleBulkImport = async () => {
    if (!importText.trim()) {
      alert("プロキシリストを入力してください")
      return
    }

    setImportLoading(true)

    try {
      const response = await axios.post(`${API_URL}/proxy-ips/bulk-import`, {
        raw_text: importText,
        proxy_type: "http",
        is_residential: false,
        source: "manual_import"
      })

      alert(
        `インポート完了\n` +
        `追加: ${response.data.added}\n` +
        `スキップ: ${response.data.skipped_duplicates}\n` +
        `無効: ${response.data.invalid}`
      )

      setImportText("")
      setImportDialogOpen(false)
      fetchProxies()
      fetchStats()
    } catch (err: any) {
      alert(err.response?.data?.detail || "インポートに失敗しました")
    } finally {
      setImportLoading(false)
    }
  }

  const handleTestAll = async () => {
    if (!confirm("全てのアクティブなプロキシをテストしますか？\nこの処理には時間がかかる場合があります。")) {
      return
    }

    setTestingAll(true)

    try {
      const response = await axios.post(`${API_URL}/proxy-ips/test`, {
        test_all: true
      })

      alert(`${response.data.tested_count}件のプロキシをテストしました`)
      fetchProxies()
      fetchStats()
    } catch (err: any) {
      alert(err.response?.data?.detail || "テストに失敗しました")
    } finally {
      setTestingAll(false)
    }
  }

  const handleTestSingle = async (proxyId: number) => {
    try {
      await axios.post(`${API_URL}/proxy-ips/test`, {
        proxy_ids: [proxyId]
      })

      alert("テスト完了")
      fetchProxies()
    } catch (err: any) {
      alert(err.response?.data?.detail || "テストに失敗しました")
    }
  }

  const handleToggleActive = async (proxyId: number, currentActive: boolean) => {
    try {
      await axios.patch(`${API_URL}/proxy-ips/${proxyId}`, {
        is_active: !currentActive
      })

      fetchProxies()
    } catch (err: any) {
      alert(err.response?.data?.detail || "更新に失敗しました")
    }
  }

  const handleDelete = async (proxyId: number) => {
    if (!confirm("このプロキシを削除しますか?")) {
      return
    }

    try {
      await axios.delete(`${API_URL}/proxy-ips/${proxyId}`)
      fetchProxies()
      fetchStats()
    } catch (err: any) {
      alert(err.response?.data?.detail || "削除に失敗しました")
    }
  }

  const handleFilterHighQuality = async () => {
    setLoading(true)

    try {
      const response = await axios.post(`${API_URL}/proxy-ips/filter`, {
        quality_levels: ["excellent", "good"],
        is_active: true,
        min_success_rate: 0.8
      })

      setProxies(response.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || "フィルタリングに失敗しました")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">プロキシIP管理</h1>
          <p className="text-gray-500 mt-1">Bot検知回避・監視設定</p>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => setImportDialogOpen(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            一括インポート
          </button>

          <button
            onClick={handleTestAll}
            disabled={testingAll}
            className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
          >
            {testingAll ? "テスト中..." : "全てテスト"}
          </button>

          <button
            onClick={handleFilterHighQuality}
            className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700"
          >
            高品質のみ表示
          </button>
        </div>
      </div>

      {/* 統計 */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-500">総数</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-500">アクティブ</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">{stats.active}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-500">レジデンシャル</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">{stats.residential}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-500">優良</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">{stats.quality_breakdown.excellent}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-500">良好</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">{stats.quality_breakdown.good}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* フィルター */}
      <Card>
        <CardHeader>
          <CardTitle>フィルター</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">品質</label>
              <select
                value={selectedQuality}
                onChange={(e) => setSelectedQuality(e.target.value)}
                className="px-3 py-2 border rounded-md"
              >
                <option value="all">全て</option>
                <option value="excellent">優良</option>
                <option value="good">良好</option>
                <option value="fair">普通</option>
                <option value="poor">低品質</option>
                <option value="untested">未テスト</option>
              </select>
            </div>

            <div className="flex items-end">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={showActiveOnly}
                  onChange={(e) => setShowActiveOnly(e.target.checked)}
                  className="mr-2"
                />
                アクティブのみ
              </label>
            </div>

            <div className="flex items-end">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={showResidentialOnly}
                  onChange={(e) => setShowResidentialOnly(e.target.checked)}
                  className="mr-2"
                />
                レジデンシャルのみ
              </label>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* エラー表示 */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-md text-red-700">
          {error}
        </div>
      )}

      {/* プロキシリスト */}
      <Card>
        <CardHeader>
          <CardTitle>プロキシリスト ({proxies.length}件)</CardTitle>
          <CardDescription>使用IP/Proxyリスト - 質の良いIPのみ表示</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-gray-500">読み込み中...</div>
          ) : proxies.length === 0 ? (
            <div className="text-center py-8 text-gray-500">プロキシがありません</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left">IP:PORT</th>
                    <th className="px-4 py-3 text-left">タイプ</th>
                    <th className="px-4 py-3 text-left">品質</th>
                    <th className="px-4 py-3 text-right">応答時間</th>
                    <th className="px-4 py-3 text-right">成功率</th>
                    <th className="px-4 py-3 text-right">リクエスト数</th>
                    <th className="px-4 py-3 text-left">国</th>
                    <th className="px-4 py-3 text-left">最終テスト</th>
                    <th className="px-4 py-3 text-center">アクション</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {proxies.map((proxy) => (
                    <tr key={proxy.id} className={proxy.is_banned ? "bg-red-50" : ""}>
                      <td className="px-4 py-3 font-mono">
                        {proxy.ip_address}:{proxy.port}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1">
                          <span className="text-xs px-2 py-1 bg-gray-100 rounded">
                            {proxy.proxy_type}
                          </span>
                          {proxy.is_residential && (
                            <span className="text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded">
                              住宅
                            </span>
                          )}
                          {proxy.is_mobile && (
                            <span className="text-xs px-2 py-1 bg-green-100 text-green-800 rounded">
                              モバイル
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs px-2 py-1 rounded ${QUALITY_COLORS[proxy.quality as keyof typeof QUALITY_COLORS]}`}>
                          {QUALITY_LABELS[proxy.quality as keyof typeof QUALITY_LABELS]}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {proxy.response_time_ms ? `${proxy.response_time_ms.toFixed(0)}ms` : "-"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className={proxy.success_rate > 0.8 ? "text-green-600 font-semibold" : ""}>
                          {(proxy.success_rate * 100).toFixed(1)}%
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">{proxy.total_requests}</td>
                      <td className="px-4 py-3">{proxy.country_code || "-"}</td>
                      <td className="px-4 py-3 text-xs text-gray-500">
                        {proxy.last_tested_at
                          ? new Date(proxy.last_tested_at).toLocaleString("ja-JP")
                          : "未テスト"}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex justify-center gap-2">
                          <button
                            onClick={() => handleTestSingle(proxy.id)}
                            className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                          >
                            テスト
                          </button>
                          <button
                            onClick={() => handleToggleActive(proxy.id, proxy.is_active)}
                            className={`text-xs px-2 py-1 rounded ${
                              proxy.is_active
                                ? "bg-yellow-100 text-yellow-700 hover:bg-yellow-200"
                                : "bg-green-100 text-green-700 hover:bg-green-200"
                            }`}
                          >
                            {proxy.is_active ? "無効化" : "有効化"}
                          </button>
                          <button
                            onClick={() => handleDelete(proxy.id)}
                            className="text-xs px-2 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200"
                          >
                            削除
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* インポートダイアログ */}
      {importDialogOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto">
          <div className="bg-white rounded-lg p-6 max-w-4xl w-full mx-4 my-8">
            <h2 className="text-xl font-bold mb-4">プロキシ一括インポート</h2>

            <div className="space-y-4">
              {!showExtractPreview ? (
                <>
                  {/* テキスト入力エリア */}
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      プロキシリスト（1行に1つ）
                    </label>
                    <textarea
                      value={importText}
                      onChange={(e) => setImportText(e.target.value)}
                      placeholder={`対応形式:\nIP:PORT\nIP:PORT:USER:PASS\nUSER:PASS@IP:PORT\nhttp://IP:PORT\nsocks5://IP:PORT`}
                      rows={15}
                      className="w-full px-3 py-2 border rounded-md font-mono text-sm"
                    />
                  </div>

                  <div className="text-sm text-gray-600">
                    <p className="font-medium mb-1">サポートされる形式:</p>
                    <ul className="list-disc list-inside space-y-1 text-xs">
                      <li>IP:PORT (例: 192.168.1.1:8080)</li>
                      <li>IP:PORT:USER:PASS (例: 192.168.1.1:8080:user:pass)</li>
                      <li>USER:PASS@IP:PORT (例: user:pass@192.168.1.1:8080)</li>
                      <li>http://IP:PORT または socks5://IP:PORT</li>
                    </ul>
                  </div>

                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => {
                        setImportDialogOpen(false)
                        setImportText("")
                      }}
                      className="px-4 py-2 border rounded-md hover:bg-gray-50"
                    >
                      キャンセル
                    </button>
                    <button
                      onClick={handleExtractIPs}
                      className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
                    >
                      IP抽出・プレビュー
                    </button>
                    <button
                      onClick={handleBulkImport}
                      disabled={importLoading}
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                    >
                      {importLoading ? "インポート中..." : "直接インポート"}
                    </button>
                  </div>
                </>
              ) : (
                <>
                  {/* IP抽出プレビュー */}
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <h3 className="text-lg font-semibold">抽出されたプロキシ ({extractedIPs.length}件)</h3>
                      <button
                        onClick={() => {
                          setShowExtractPreview(false)
                          setExtractedIPs([])
                        }}
                        className="text-sm text-blue-600 hover:underline"
                      >
                        ← テキスト編集に戻る
                      </button>
                    </div>

                    <div className="border rounded-md max-h-96 overflow-y-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-gray-50 sticky top-0">
                          <tr>
                            <th className="px-3 py-2 text-left">IP</th>
                            <th className="px-3 py-2 text-left">ポート</th>
                            <th className="px-3 py-2 text-left">タイプ</th>
                            <th className="px-3 py-2 text-left">認証</th>
                            <th className="px-3 py-2 text-left">元テキスト</th>
                            <th className="px-3 py-2 text-center">操作</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y">
                          {extractedIPs.map((ip, index) => (
                            <tr key={index} className="hover:bg-gray-50">
                              <td className="px-3 py-2 font-mono text-xs">{ip.ip_address}</td>
                              <td className="px-3 py-2">{ip.port}</td>
                              <td className="px-3 py-2">
                                <span className="text-xs px-2 py-1 bg-gray-100 rounded">
                                  {ip.proxy_type}
                                </span>
                              </td>
                              <td className="px-3 py-2">
                                {ip.username ? (
                                  <span className="text-xs px-2 py-1 bg-green-100 text-green-800 rounded">
                                    あり
                                  </span>
                                ) : (
                                  <span className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded">
                                    なし
                                  </span>
                                )}
                              </td>
                              <td className="px-3 py-2 font-mono text-xs text-gray-500 truncate max-w-xs">
                                {ip.original}
                              </td>
                              <td className="px-3 py-2 text-center">
                                <button
                                  onClick={() => handleRemoveExtracted(index)}
                                  className="text-xs px-2 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200"
                                >
                                  削除
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
                    <p className="text-sm text-blue-800">
                      <strong>{extractedIPs.length}件</strong>のプロキシが抽出されました。
                      不要なものは削除ボタンで除外できます。
                    </p>
                  </div>

                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => {
                        setShowExtractPreview(false)
                        setExtractedIPs([])
                        setImportDialogOpen(false)
                        setImportText("")
                      }}
                      className="px-4 py-2 border rounded-md hover:bg-gray-50"
                    >
                      キャンセル
                    </button>
                    <button
                      onClick={handleImportExtracted}
                      disabled={importLoading || extractedIPs.length === 0}
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                    >
                      {importLoading ? "インポート中..." : `${extractedIPs.length}件をインポート`}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
