export type Session = {
  userId: string
  name: string
  email: string
  role: "Diligence Analyst"
}

export interface AuthAdapter {
  signIn(email: string, password: string): Promise<Session>
  signUp(name: string, email: string, password: string): Promise<Session>
  signOut(): Promise<void>
  getSession(): Promise<Session | null>
}

