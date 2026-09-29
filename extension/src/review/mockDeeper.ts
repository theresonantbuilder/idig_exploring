// "iDIG Deeper" — 2-3 resources per trail, attached directly under that
// trail's card rather than a separate gallery. Deliberately mixed sources
// (not only Amazon affiliate) so it reads as genuinely useful, not a
// merchandising rail. Titles/sources are placeholders — no real recall or
// real links yet (see mockDig.ts for the same caveat on the dig content).

import type { TrailCandidate } from './mockDig';

export type ResourceType = 'book' | 'course' | 'podcast' | 'video' | 'article' | 'exhibit';

export interface DeeperResource {
  type: ResourceType;
  title: string;
  source: string; // where it lives — "Amazon", "Free article — ...", "YouTube", "Coursera", etc.
  reason: string; // ties it to THIS trail's question specifically, not just its category
  url: string; // placeholder for mock entries, real URL from the Deeper pipeline otherwise
  affiliate?: boolean; // mock-only flag; the real pipeline never sets this
}

export const MOCK_DEEPER: Partial<Record<TrailCandidate['move'], DeeperResource[]>> = {
  tension: [
    {
      type: 'book',
      title: 'How Databases Decide Who Belongs',
      source: 'Amazon',
      reason: 'On systems built for one purpose getting repurposed for another.',
      url: '#',
      affiliate: true,
    },
    {
      type: 'article',
      title: 'The Quiet Repurposing of SAVE',
      source: 'Free article — The Conversation',
      reason: "A shorter history of SAVE's original benefits-eligibility purpose.",
      url: '#',
      affiliate: false,
    },
  ],
  mechanism: [
    {
      type: 'course',
      title: 'Data Matching and Record Linkage',
      source: 'Coursera',
      reason: 'Explains the matching techniques behind tools like SAVE.',
      url: '#',
      affiliate: false,
    },
    {
      type: 'video',
      title: 'Inside a Record-Matching Algorithm',
      source: 'YouTube',
      reason: 'A visual walkthrough of how false positives happen.',
      url: '#',
      affiliate: false,
    },
  ],
  precedent: [
    {
      type: 'book',
      title: 'The Purge',
      source: 'Amazon',
      reason: 'A history of prior voter-roll purge attempts and how they ended.',
      url: '#',
      affiliate: true,
    },
    {
      type: 'video',
      title: 'Who Counts',
      source: 'PBS',
      reason: "Documents an earlier state's purge and its aftermath.",
      url: '#',
      affiliate: false,
    },
  ],
  frame: [
    {
      type: 'article',
      title: 'Two Words, One Policy',
      source: 'Free article — Poynter',
      reason: 'On how "integrity" and "suppression" get used for the same policy.',
      url: '#',
      affiliate: false,
    },
    {
      type: 'video',
      title: 'The Language of Election Integrity',
      source: 'YouTube',
      reason: 'Traces how this framing language entered political use.',
      url: '#',
      affiliate: false,
    },
  ],
  stakes: [
    {
      type: 'book',
      title: 'Flagged',
      source: 'Amazon',
      reason: 'Follows individuals through the experience of being wrongly flagged.',
      url: '#',
      affiliate: true,
    },
    {
      type: 'podcast',
      title: 'Citizenship by Algorithm',
      source: 'Podcast — independent',
      reason: 'An episode centers on the Texas reinstatement cases.',
      url: '#',
      affiliate: false,
    },
  ],
  hidden: [
    {
      type: 'exhibit',
      title: 'Voting Rights Exhibit',
      source: 'National Archives',
      reason: 'Covers the officials and processes behind voter-roll decisions historically.',
      url: '#',
      affiliate: false,
    },
    {
      type: 'book',
      title: 'Database of the Vulnerable',
      source: 'Amazon',
      reason: 'On who actually reviews a flagged record before anything happens.',
      url: '#',
      affiliate: true,
    },
  ],
  scale: [
    {
      type: 'article',
      title: 'Doing the Math on Voter Fraud Claims',
      source: 'Free article — FactCheck.org',
      reason: 'Puts the 28,635 flagged figure in context against prior estimates.',
      url: '#',
      affiliate: false,
    },
    {
      type: 'podcast',
      title: 'The Data Republic',
      source: 'Podcast — independent',
      reason: 'An episode is specifically about SAVE’s scale-up in 2025.',
      url: '#',
      affiliate: false,
    },
  ],
  unknowns: [
    {
      type: 'course',
      title: 'Auditing Algorithmic Systems',
      source: 'edX',
      reason: 'Covers what an independent accuracy audit actually requires.',
      url: '#',
      affiliate: false,
    },
    {
      type: 'video',
      title: 'How to Audit a Government Database',
      source: 'YouTube',
      reason: 'A practical explainer aimed at journalists and researchers.',
      url: '#',
      affiliate: false,
    },
  ],
};
