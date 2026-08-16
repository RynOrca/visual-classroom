export interface Chapter {
  id: string
  title: string
  source: string
  notebook?: string | null
  order_index: number
  summary?: string | null
  page_start?: number | null
  page_end?: number | null
}

export interface KnowledgePoint {
  id: string
  title: string
  source: string
  chapter?: string | null
  notebook?: string | null
  page_number?: number | null
  summary?: string | null
  tags: string[]
  hotness?: number
}

export interface QuizQuestion {
  id: string
  type: string
  question: string
  options: string[]
  correct_index: number
  correct_answer: string
  explanation: string
}

export interface QuizSession {
  id: string
  source?: string | null
  notebook?: string | null
  total_questions: number
  correct_count: number
  score: number
  details?: string | null
}

export interface QuizResult {
  index: number
  correct: boolean
  user_answer: string
  correct_answer: string
  explanation: string
}

export interface QuizSubmitResponse {
  session_id: string
  total_questions: number
  correct_count: number
  score: number
  results: QuizResult[]
}

export interface Mistake {
  id: string
  source: string
  notebook?: string | null
  knowledge_point?: string | null
  page_number?: number | null
  quiz_type: string
  question: string
  options?: string[] | null
  correct_answer: string
  user_answer: string
  is_correct: boolean
  mastered_at?: string | null
  tags: string[]
}

export interface ConversationNote {
  id: string
  chat_session?: string | null
  source?: string | null
  notebook?: string | null
  knowledge_point?: string | null
  question: string
  answer: string
  note_type: string
  tags: string[]
  created?: string | null
}

export interface ReviewRouteData {
  title?: string
  overview?: string
  stages?: Array<{
    stage_id?: string
    stage_label?: string
    why?: string
    drill?: Array<{
      title?: string
      summary?: string
      knowledge_point_id?: string | null
      conversation_note_ids?: string[]
      mistake_ids?: string[]
    }>
  }>
}

export interface ReviewRouteResponse {
  id: string
  notebook?: string | null
  source?: string | null
  data: string
  status: string
}
