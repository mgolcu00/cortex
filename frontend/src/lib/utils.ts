import { clsx, type ClassValue } from 'clsx'

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs)
}

export function formatNumber(num: number): string {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K'
  }
  return num.toLocaleString()
}

export function formatCurrency(amount: number): string {
  if (amount < 0.01) {
    return `$${amount.toFixed(6)}`
  }
  return `$${amount.toFixed(4)}`
}

export function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${ms}ms`
  }
  return `${(ms / 1000).toFixed(1)}s`
}

export function formatDate(dateString: string | null): string {
  if (!dateString) return '-'

  const date = new Date(dateString)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 60000) {
    return 'Az once'
  }

  if (diff < 3600000) {
    const minutes = Math.floor(diff / 60000)
    return `${minutes} dk once`
  }

  if (diff < 86400000) {
    const hours = Math.floor(diff / 3600000)
    return `${hours} saat once`
  }

  if (diff < 604800000) {
    const days = Math.floor(diff / 86400000)
    return `${days} gun once`
  }

  return date.toLocaleDateString('tr-TR', {
    day: '2-digit',
    month: 'short',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  })
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str
  return str.slice(0, length) + '...'
}

export function generateId(): string {
  return crypto.randomUUID()
}
