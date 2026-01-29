export type ToastType = 'error' | 'warning' | 'info'

export interface Toast {
  id: string
  message: string
  type: ToastType
  createdAt: number
}

export interface ErrorModalState {
  title: string
  message: string
}
