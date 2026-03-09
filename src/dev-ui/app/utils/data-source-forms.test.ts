import { describe, it, expect } from 'vitest'
import {
  validateGitHubAdapter,
  hasGitHubErrors,
  buildGitHubConnectionConfig,
  buildGitHubCredentials,
} from './data-source-forms'

describe('validateGitHubAdapter', () => {
  it('returns no errors for fully valid fields', () => {
    const errors = validateGitHubAdapter({
      owner: 'my-org',
      repo: 'my-repo',
      branch: 'main',
      token: 'ghp_abc123',
    })
    expect(errors.owner).toBe('')
    expect(errors.repo).toBe('')
    expect(errors.token).toBe('')
  })

  it('returns error when owner is empty', () => {
    const errors = validateGitHubAdapter({ owner: '', repo: 'repo', branch: '', token: 'tok' })
    expect(errors.owner).toBe('GitHub owner is required')
  })

  it('returns error when owner is whitespace only', () => {
    const errors = validateGitHubAdapter({ owner: '   ', repo: 'repo', branch: '', token: 'tok' })
    expect(errors.owner).toBe('GitHub owner is required')
  })

  it('returns error when repo is empty', () => {
    const errors = validateGitHubAdapter({ owner: 'org', repo: '', branch: '', token: 'tok' })
    expect(errors.repo).toBe('Repository name is required')
  })

  it('returns error when token is empty', () => {
    const errors = validateGitHubAdapter({ owner: 'org', repo: 'repo', branch: '', token: '' })
    expect(errors.token).toBe('Personal Access Token is required')
  })

  it('returns error when token is whitespace only', () => {
    const errors = validateGitHubAdapter({ owner: 'org', repo: 'repo', branch: '', token: '  ' })
    expect(errors.token).toBe('Personal Access Token is required')
  })

  it('does not require branch', () => {
    const errors = validateGitHubAdapter({ owner: 'org', repo: 'repo', branch: '', token: 'tok' })
    expect(errors.owner).toBe('')
    expect(errors.repo).toBe('')
    expect(errors.token).toBe('')
  })

  it('returns multiple errors simultaneously', () => {
    const errors = validateGitHubAdapter({ owner: '', repo: '', branch: '', token: '' })
    expect(errors.owner).toBeTruthy()
    expect(errors.repo).toBeTruthy()
    expect(errors.token).toBeTruthy()
  })
})

describe('hasGitHubErrors', () => {
  it('returns false when all errors are empty strings', () => {
    expect(hasGitHubErrors({ owner: '', repo: '', token: '' })).toBe(false)
  })

  it('returns true when any error is set', () => {
    expect(hasGitHubErrors({ owner: 'required', repo: '', token: '' })).toBe(true)
    expect(hasGitHubErrors({ owner: '', repo: 'required', token: '' })).toBe(true)
    expect(hasGitHubErrors({ owner: '', repo: '', token: 'required' })).toBe(true)
  })
})

describe('buildGitHubConnectionConfig', () => {
  it('includes owner and repo', () => {
    const config = buildGitHubConnectionConfig({ owner: 'my-org', repo: 'my-repo', branch: '', token: 'tok' })
    expect(config.owner).toBe('my-org')
    expect(config.repo).toBe('my-repo')
  })

  it('includes branch when provided', () => {
    const config = buildGitHubConnectionConfig({ owner: 'org', repo: 'repo', branch: 'feature', token: 'tok' })
    expect(config.branch).toBe('feature')
  })

  it('omits branch when empty', () => {
    const config = buildGitHubConnectionConfig({ owner: 'org', repo: 'repo', branch: '', token: 'tok' })
    expect('branch' in config).toBe(false)
  })

  it('omits branch when whitespace only', () => {
    const config = buildGitHubConnectionConfig({ owner: 'org', repo: 'repo', branch: '  ', token: 'tok' })
    expect('branch' in config).toBe(false)
  })

  it('trims whitespace from owner and repo', () => {
    const config = buildGitHubConnectionConfig({ owner: '  org  ', repo: '  repo  ', branch: '', token: 'tok' })
    expect(config.owner).toBe('org')
    expect(config.repo).toBe('repo')
  })
})

describe('buildGitHubCredentials', () => {
  it('returns token credential', () => {
    const creds = buildGitHubCredentials({ owner: 'org', repo: 'repo', branch: '', token: 'ghp_abc123' })
    expect(creds.token).toBe('ghp_abc123')
  })

  it('trims whitespace from token', () => {
    const creds = buildGitHubCredentials({ owner: 'org', repo: 'repo', branch: '', token: '  ghp_abc  ' })
    expect(creds.token).toBe('ghp_abc')
  })
})
