export interface GitHubAdapterFields {
  owner: string
  repo: string
  branch: string
  token: string
}

export interface GitHubValidationErrors {
  owner: string
  repo: string
  token: string
}

export function validateGitHubAdapter(fields: GitHubAdapterFields): GitHubValidationErrors {
  return {
    owner: fields.owner.trim() ? '' : 'GitHub owner is required',
    repo: fields.repo.trim() ? '' : 'Repository name is required',
    token: fields.token.trim() ? '' : 'Personal Access Token is required',
  }
}

export function hasGitHubErrors(errors: GitHubValidationErrors): boolean {
  return !!(errors.owner || errors.repo || errors.token)
}

export function buildGitHubConnectionConfig(fields: GitHubAdapterFields): Record<string, string> {
  const config: Record<string, string> = {
    owner: fields.owner.trim(),
    repo: fields.repo.trim(),
  }
  if (fields.branch.trim()) {
    config.branch = fields.branch.trim()
  }
  return config
}

export function buildGitHubCredentials(fields: GitHubAdapterFields): Record<string, string> {
  return { token: fields.token.trim() }
}
