// What passes between the buyer and the merchandiser: the order timeline.

export interface ActivityItem { at: string; kind: "date" | "step" | "request" | "notice"; actor: string; title: string; detail: string | null }
