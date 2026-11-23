/** The element an event really started on, through any shadow boundary (a window listener may see only a host). */
export function eventOrigin(e: Event): EventTarget | null { return (e.composedPath?.()[0] as EventTarget | undefined) ?? e.target; }
