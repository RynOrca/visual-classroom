'use client'

import { AppShell } from '@/components/layout/AppShell'

export default function VirtualClassroomPage() {
  return (
    <AppShell>
      <div className="flex-1 overflow-y-auto p-6">
        <h1 className="font-display text-2xl font-bold tracking-tight">
          Virtual Classroom
        </h1>
        <p className="text-muted-foreground mt-2">
          V3 虚拟课堂模块：章节、知识点、知识地图、错题本将在这里逐步接入。
        </p>
      </div>
    </AppShell>
  )
}
