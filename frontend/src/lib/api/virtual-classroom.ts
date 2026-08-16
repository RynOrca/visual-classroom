import apiClient from './client'
import {
  Chapter,
  ConversationNote,
  KnowledgePoint,
  QuizQuestion,
  QuizSession,
  QuizSubmitResponse,
  Mistake,
} from '@/lib/types/virtual-classroom'

export const virtualClassroomApi = {
  // Chapters
  listChapters: async (params?: { source_id?: string; notebook_id?: string }) => {
    const response = await apiClient.get<Chapter[]>('/virtual-classroom/chapters', { params })
    return response.data
  },
  extractChapters: async (data: { source_id: string; notebook_id?: string }) => {
    const response = await apiClient.post<Chapter[]>('/virtual-classroom/extract-chapters', data)
    return response.data
  },

  // Knowledge points
  listKnowledgePoints: async (params?: { source_id?: string; chapter_id?: string; notebook_id?: string }) => {
    const response = await apiClient.get<KnowledgePoint[]>('/virtual-classroom/knowledge-points', { params })
    return response.data
  },
  extractKnowledgePoints: async (data: { source_id: string; notebook_id?: string; chapter_id?: string }) => {
    const response = await apiClient.post<KnowledgePoint[]>('/virtual-classroom/extract-knowledge-points', data)
    return response.data
  },

  // Quiz
  generateQuiz: async (data: {
    source_id: string
    notebook_id?: string
    chapter_id?: string
    count?: number
    question_types?: string[]
  }) => {
    const response = await apiClient.post<{ questions: QuizQuestion[] }>('/virtual-classroom/quiz/generate', data)
    return response.data.questions
  },
  createQuizSession: async (data: {
    source_id: string
    notebook_id?: string
    chapter_id?: string
    questions: QuizQuestion[]
  }) => {
    const response = await apiClient.post<QuizSession>('/virtual-classroom/quiz/sessions', data)
    return response.data
  },
  submitQuizSession: async (sessionId: string, answers: { index: number; user_answer: string }[]) => {
    const response = await apiClient.post<QuizSubmitResponse>(`/virtual-classroom/quiz/sessions/${sessionId}/submit`, { answers })
    return response.data
  },

  // Mistakes
  listMistakes: async (params?: { source_id?: string; notebook_id?: string; mastered?: boolean }) => {
    const response = await apiClient.get<Mistake[]>('/virtual-classroom/mistakes', { params })
    return response.data
  },
  markMistakeMastered: async (id: string, mastered: boolean) => {
    const response = await apiClient.put<Mistake>(`/virtual-classroom/mistakes/${id}`, { mastered })
    return response.data
  },
}

export const conversationApi = {
  list: async (params?: { source_id?: string; notebook_id?: string; chat_session_id?: string }) => {
    const response = await apiClient.get<ConversationNote[]>('/virtual-classroom/conversation-notes', { params })
    return response.data
  },
  organize: async (data: { chat_session_id: string }) => {
    const response = await apiClient.post<ConversationNote[]>('/virtual-classroom/conversation-notes/organize', data)
    return response.data
  },
}

export interface KnowledgeMapData {
  title?: string
  storyline?: string
  stages?: Array<{
    id?: string
    label?: string
    summary?: string
    bridgeToNext?: string
    concepts?: Array<{ label?: string; brief?: string }>
  }>
}

export interface KnowledgeMapResponse {
  id: string
  notebook?: string | null
  source?: string | null
  data: string
  status: string
}

export const knowledgeMapApi = {
  get: async (params?: { notebook_id?: string; source_id?: string }) => {
    const response = await apiClient.get<KnowledgeMapResponse>('/virtual-classroom/knowledge-map', { params })
    return response.data
  },
  generate: async (data: { notebook_id?: string; source_id?: string }) => {
    const response = await apiClient.post<KnowledgeMapResponse>('/virtual-classroom/knowledge-map/generate', data)
    return response.data
  },
}

export interface ReviewRouteResponse {
  id: string
  notebook?: string | null
  source?: string | null
  data: string
  status: string
}

export const reviewApi = {
  get: async (params?: { notebook_id?: string; source_id?: string }) => {
    const response = await apiClient.get<ReviewRouteResponse>('/virtual-classroom/review', { params })
    return response.data
  },
  generate: async (data: { notebook_id?: string; source_id?: string }) => {
    const response = await apiClient.post<ReviewRouteResponse>('/virtual-classroom/review/generate', data)
    return response.data
  },
}
