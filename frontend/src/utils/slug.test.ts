import { describe, it, expect } from 'vitest'
import { wikiSlugToPath, slugToTitle } from './slug'

describe('wikiSlugToPath', () => {
  it('converts slug with extension to path', () => {
    expect(wikiSlugToPath('lib-MooseX-Extended-pm')).toBe('lib/MooseX/Extended.pm')
  })

  it('converts directory slug to path', () => {
    expect(wikiSlugToPath('src-api')).toBe('src/api')
  })

  it('handles single segment', () => {
    expect(wikiSlugToPath('README')).toBe('README')
  })
})

describe('slugToTitle', () => {
  it('converts simple slug to title case', () => {
    expect(slugToTitle('jobs')).toBe('Jobs')
  })

  it('converts multi-word slug to title case', () => {
    expect(slugToTitle('route-workflows')).toBe('Route Workflows')
  })

  it('handles common abbreviations as uppercase', () => {
    expect(slugToTitle('qa')).toBe('QA')
    expect(slugToTitle('api-routes')).toBe('API Routes')
    expect(slugToTitle('user-api')).toBe('User API')
  })

  it('handles version strings as uppercase', () => {
    expect(slugToTitle('repos-v2')).toBe('Repos V2')
    expect(slugToTitle('api-v1')).toBe('API V1')
  })

  it('handles mixed case input', () => {
    expect(slugToTitle('WIKI')).toBe('Wiki')
    expect(slugToTitle('RUN')).toBe('Run')
  })

  it('handles multiple abbreviations', () => {
    expect(slugToTitle('api-cli-tools')).toBe('API CLI Tools')
  })

  it('handles database abbreviation', () => {
    expect(slugToTitle('db-connection')).toBe('DB Connection')
  })

  it('handles URL and HTTP abbreviations', () => {
    expect(slugToTitle('url-parser')).toBe('URL Parser')
    expect(slugToTitle('http-client')).toBe('HTTP Client')
  })
})
