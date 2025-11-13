import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import Navigation from '@/components/Navigation'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: '釈迦AI - プロンプトベースSNS自動化',
  description: '自然言語でSNSを操作する次世代AIエージェントシステム',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ja">
      <body className={inter.className}>
        <Navigation />
        {children}
      </body>
    </html>
  )
}
