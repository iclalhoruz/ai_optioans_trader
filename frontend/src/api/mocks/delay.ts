// Mock resolvers go through this instead of returning instantly, so loading
// states actually get exercised during dev instead of only showing up the
// first time a real, slower backend is wired in.
export function delay<T>(value: T, ms = 400): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms))
}
