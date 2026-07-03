import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useRepoStore = create(
  persist(
    (set, get) => ({
      repositories: [],
      upsertFromSync(result) {
        const name = result.repo
        const existing = get().repositories.find((r) => r.name === name)
        const entry = {
          id: existing?.id || `repo-${name}`,
          name,
          url: `https://github.com/${name}`,
          status: result.mode === 'skipped' ? 'indexed' : 'indexed',
          files: result.files_indexed ?? existing?.files ?? 0,
          chunks: result.chunks_written ?? existing?.chunks ?? 0,
          lastIndexed: Date.now(),
        }
        set({
          repositories: [
            entry,
            ...get().repositories.filter((r) => r.name !== name),
          ],
        })
      },
      setIndexing(name) {
        const existing = get().repositories.find((r) => r.name === name)
        const entry = {
          id: existing?.id || `repo-${name}`,
          name,
          url: `https://github.com/${name}`,
          status: 'indexing',
          files: existing?.files ?? 0,
          chunks: existing?.chunks ?? 0,
        }
        set({
          repositories: [
            entry,
            ...get().repositories.filter((r) => r.name !== name),
          ],
        })
      },
      markFailed(name) {
        set({
          repositories: get().repositories.map((r) =>
            r.name === name ? { ...r, status: 'failed' } : r,
          ),
        })
      },
    }),
    { name: 'issue-resolver-repos' },
  ),
)
