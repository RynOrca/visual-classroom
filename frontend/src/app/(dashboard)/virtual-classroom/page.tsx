'use client'

import { useEffect, useMemo, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useNotebooks } from '@/lib/hooks/use-notebooks'
import { useNotebookSources } from '@/lib/hooks/use-sources'
import { virtualClassroomApi, knowledgeMapApi } from '@/lib/api/virtual-classroom'
import type { KnowledgeMapData } from '@/lib/api/virtual-classroom'
import {
  Chapter,
  KnowledgePoint,
  Mistake,
  QuizQuestion,
  QuizSubmitResponse,
} from '@/lib/types/virtual-classroom'

export default function VirtualClassroomPage() {
  const { data: notebooks } = useNotebooks(false)
  const [notebookId, setNotebookId] = useState('')
  const [sourceId, setSourceId] = useState('')

  const { sources } = useNotebookSources(notebookId || '')
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [knowledgePoints, setKnowledgePoints] = useState<KnowledgePoint[]>([])
  const [knowledgeMap, setKnowledgeMap] = useState<KnowledgeMapData | null>(null)
  const [generatingMap, setGeneratingMap] = useState(false)
  const [mistakes, setMistakes] = useState<Mistake[]>([])

  const [extractingChapters, setExtractingChapters] = useState(false)
  const [extractingKps, setExtractingKps] = useState(false)

  const [quizQuestions, setQuizQuestions] = useState<QuizQuestion[]>([])
  const [quizAnswers, setQuizAnswers] = useState<Record<number, string>>({})
  const [quizSessionId, setQuizSessionId] = useState<string | null>(null)
  const [quizResult, setQuizResult] = useState<QuizSubmitResponse | null>(null)
  const [generatingQuiz, setGeneratingQuiz] = useState(false)
  const [submittingQuiz, setSubmittingQuiz] = useState(false)

  const activeNotebook = useMemo(
    () => notebooks?.find((n) => n.id === notebookId),
    [notebooks, notebookId]
  )

  useEffect(() => {
    if (!notebooks || notebooks.length === 0) return
    if (!notebookId) {
      setNotebookId(notebooks[0].id)
      return
    }
  }, [notebooks, notebookId])

  useEffect(() => {
    if (!sourceId) return
    let cancelled = false
    Promise.all([
      virtualClassroomApi.listChapters({ source_id: sourceId, notebook_id: notebookId || undefined }),
      virtualClassroomApi.listKnowledgePoints({ source_id: sourceId, notebook_id: notebookId || undefined }),
      virtualClassroomApi.listMistakes({ source_id: sourceId, notebook_id: notebookId || undefined }),
    ])
      .then(([chs, kps, mis]) => {
        if (cancelled) return
        setChapters(chs)
        setKnowledgePoints(kps)
        setMistakes(mis)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [sourceId, notebookId])

  const handleExtractChapters = async () => {
    if (!sourceId) return
    setExtractingChapters(true)
    try {
      const chs = await virtualClassroomApi.extractChapters({
        source_id: sourceId,
        notebook_id: notebookId || undefined,
      })
      setChapters(chs)
    } catch (error) {
      console.error(error)
    } finally {
      setExtractingChapters(false)
    }
  }

  const handleExtractKps = async () => {
    if (!sourceId) return
    setExtractingKps(true)
    try {
      const kps = await virtualClassroomApi.extractKnowledgePoints({
        source_id: sourceId,
        notebook_id: notebookId || undefined,
      })
      setKnowledgePoints(kps)
    } catch (error) {
      console.error(error)
    } finally {
      setExtractingKps(false)
    }
  }

  const handleGenerateKnowledgeMap = async () => {
    if (!sourceId && !notebookId) return
    setGeneratingMap(true)
    try {
      const res = await knowledgeMapApi.generate({
        notebook_id: notebookId || undefined,
        source_id: sourceId || undefined,
      })
      setKnowledgeMap(JSON.parse(res.data || '{}'))
    } catch (error) {
      console.error(error)
    } finally {
      setGeneratingMap(false)
    }
  }


  const handleGenerateQuiz = async () => {
    if (!sourceId) return
    setGeneratingQuiz(true)
    setQuizResult(null)
    setQuizAnswers({})
    try {
      const questions = await virtualClassroomApi.generateQuiz({
        source_id: sourceId,
        notebook_id: notebookId || undefined,
        count: 3,
        question_types: ['single_choice'],
      })
      setQuizQuestions(questions)
    } catch (error) {
      console.error(error)
    } finally {
      setGeneratingQuiz(false)
    }
  }

  const handleStartQuiz = async () => {
    if (!sourceId || quizQuestions.length === 0) return
    try {
      const session = await virtualClassroomApi.createQuizSession({
        source_id: sourceId,
        notebook_id: notebookId || undefined,
        questions: quizQuestions,
      })
      setQuizSessionId(session.id)
    } catch (error) {
      console.error(error)
    }
  }

  const handleSubmitQuiz = async () => {
    if (!quizSessionId) return
    setSubmittingQuiz(true)
    try {
      const answers = quizQuestions.map((_, index) => ({
        index,
        user_answer: quizAnswers[index] || '',
      }))
      const result = await virtualClassroomApi.submitQuizSession(quizSessionId, answers)
      setQuizResult(result)
      const mis = await virtualClassroomApi.listMistakes({
        source_id: sourceId,
        notebook_id: notebookId || undefined,
      })
      setMistakes(mis)
    } catch (error) {
      console.error(error)
    } finally {
      setSubmittingQuiz(false)
    }
  }

  const handleMarkMastered = async (id: string, mastered: boolean) => {
    await virtualClassroomApi.markMistakeMastered(id, mastered)
    setMistakes((prev) =>
      prev.map((m) => (m.id === id ? { ...m, mastered_at: mastered ? new Date().toISOString() : null } : m))
    )
  }

  return (
    <AppShell>
      <div className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-6">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight">Virtual Classroom</h1>
            <p className="text-muted-foreground text-sm mt-1">
              V3 虚拟课堂：选择课件后，自动抽取章节/知识点，并支持刷题与错题本。
            </p>
          </div>

          {/* Selectors */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="notebook">科目 / Notebook</Label>
              <select
                id="notebook"
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                value={notebookId}
                onChange={(e) => {
                  setNotebookId(e.target.value)
                  setSourceId('')
                  setChapters([])
                  setKnowledgePoints([])
                  setMistakes([])
                  setQuizQuestions([])
                  setQuizResult(null)
                }}
              >
                {notebooks?.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="source">课件 / Source</Label>
              <select
                id="source"
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                value={sourceId}
                onChange={(e) => setSourceId(e.target.value)}
              >
                <option value="">请选择课件</option>
                {sources.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* AI Extraction */}
          {sourceId && (
            <div className="flex flex-wrap gap-2">
              <Button onClick={handleExtractChapters} disabled={extractingChapters}>
                {extractingChapters ? '抽取中...' : 'AI 抽取章节'}
              </Button>
              <Button onClick={handleExtractKps} disabled={extractingKps} variant="secondary">
                {extractingKps ? '抽取中...' : 'AI 抽取知识点'}
              </Button>
            </div>
          )}

          {/* Knowledge Map */}
          {(sourceId || notebookId) && (
            <div className="rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold">知识地图</h2>
                <Button onClick={handleGenerateKnowledgeMap} disabled={generatingMap} variant="outline" size="sm">
                  {generatingMap ? '生成中...' : '生成知识地图'}
                </Button>
              </div>
              {knowledgeMap ? (
                <div className="mt-3 space-y-4">
                  {knowledgeMap.title && <p className="font-medium">{knowledgeMap.title}</p>}
                  {knowledgeMap.storyline && (
                    <p className="text-sm text-muted-foreground">{knowledgeMap.storyline}</p>
                  )}
                  {knowledgeMap.stages?.map((stage, idx) => (
                    <div key={stage.id || idx} className="rounded-md border p-3">
                      <div className="font-medium">{stage.label}</div>
                      {stage.summary && <p className="text-sm text-muted-foreground mt-1">{stage.summary}</p>}
                      {stage.bridgeToNext && (
                        <p className="text-xs text-muted-foreground mt-1">→ {stage.bridgeToNext}</p>
                      )}
                      {stage.concepts && stage.concepts.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {stage.concepts.map((c, ci) => (
                            <span key={ci} className="rounded-full bg-muted px-2 py-0.5 text-xs">
                              {c.label}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground text-sm mt-2">暂无知识地图，先生成章节/知识点后再生成地图。</p>
              )}
            </div>
          )}


          {/* Chapters & Knowledge Points */}
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-lg border p-4">
              <h2 className="font-semibold">章节</h2>
              {chapters.length === 0 ? (
                <p className="text-muted-foreground text-sm mt-2">暂无章节，点击 AI 抽取章节。</p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {chapters.map((c) => (
                    <li key={c.id} className="rounded-md border p-3 text-sm">
                      <div className="font-medium">{c.order_index}. {c.title}</div>
                      {c.summary && <p className="text-muted-foreground mt-1">{c.summary}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rounded-lg border p-4">
              <h2 className="font-semibold">知识点</h2>
              {knowledgePoints.length === 0 ? (
                <p className="text-muted-foreground text-sm mt-2">暂无知识点，点击 AI 抽取知识点。</p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {knowledgePoints.map((kp) => (
                    <li key={kp.id} className="rounded-md border p-3 text-sm">
                      <div className="font-medium">{kp.title}</div>
                      {kp.summary && <p className="text-muted-foreground mt-1">{kp.summary}</p>}
                      {kp.tags.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {kp.tags.map((tag) => (
                            <span key={tag} className="rounded-full bg-muted px-2 py-0.5 text-xs">
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Quiz */}
          {sourceId && (
            <div className="rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold">刷题</h2>
                <Button onClick={handleGenerateQuiz} disabled={generatingQuiz} variant="outline" size="sm">
                  {generatingQuiz ? '生成中...' : '生成题目'}
                </Button>
              </div>

              {quizQuestions.length > 0 && (
                <div className="mt-4 space-y-4">
                  {quizQuestions.map((q, idx) => (
                    <div key={q.id} className="rounded-md border p-3">
                      <p className="text-sm font-medium">{idx + 1}. {q.question}</p>
                      <div className="mt-2 space-y-1">
                        {q.options.map((opt, optIdx) => (
                          <label key={optIdx} className="flex items-center gap-2 text-sm">
                            <input
                              type="radio"
                              name={`q-${idx}`}
                              value={String.fromCharCode(97 + optIdx)}
                              onChange={(e) =>
                                setQuizAnswers((prev) => ({ ...prev, [idx]: e.target.value }))
                              }
                            />
                            {opt}
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}

                  <div className="flex flex-wrap gap-2">
                    {!quizSessionId ? (
                      <Button onClick={handleStartQuiz}>开始答题（创建会话）</Button>
                    ) : (
                      <Button onClick={handleSubmitQuiz} disabled={submittingQuiz}>
                        {submittingQuiz ? '批改中...' : '提交答案'}
                      </Button>
                    )}
                  </div>

                  {quizResult && (
                    <div className="rounded-md bg-muted p-4">
                      <p className="font-medium">
                        得分：{quizResult.score} / 100（{quizResult.correct_count}/{quizResult.total_questions}）
                      </p>
                      <ul className="mt-2 space-y-1 text-sm">
                        {quizResult.results.map((r) => (
                          <li key={r.index}>
                            {r.correct ? '✅' : '❌'} 第{r.index + 1}题
                            {!r.correct && ` 正确答案：${r.correct_answer}`}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Mistake Book */}
          <div className="rounded-lg border p-4">
            <h2 className="font-semibold">错题本</h2>
            {mistakes.length === 0 ? (
              <p className="text-muted-foreground text-sm mt-2">暂无错题。</p>
            ) : (
              <ul className="mt-3 space-y-2">
                {mistakes.map((m) => (
                  <li key={m.id} className="rounded-md border p-3 text-sm">
                    <div className="font-medium">{m.question}</div>
                    <div className="text-muted-foreground mt-1">
                      你的答案：{m.user_answer || '（空）'} · 正确答案：{m.correct_answer}
                    </div>
                    <div className="mt-2">
                      {m.mastered_at ? (
                        <Button size="sm" variant="secondary" onClick={() => handleMarkMastered(m.id, false)}>
                          取消掌握
                        </Button>
                      ) : (
                        <Button size="sm" onClick={() => handleMarkMastered(m.id, true)}>
                          标记掌握
                        </Button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  )
}
