// A hand-researched example, laid out exactly to the SPEC §7.1 schema and the
// §5.6 reader order (source → headline → claim → what_happened → why_now →
// established → contested → left_out → still_unknown → sources → trails).
// Not from the real Gemini pipeline — Phase D/E doesn't exist yet. For
// exploring the panel's layout only; see the "Preview" tab.

import type { DeeperResource } from './mockDeeper';

export interface ContestedEntry {
  held_by: string;
  position: string;
}

// Mirrors PATTERNS in dev_server/pipeline.py — a closed vocabulary of structural/causal
// patterns (SPEC §7.3a, D35), deliberately NOT narrative archetypes: these name the
// mechanism, not the drama, so two unrelated stories can share the same tag. Built ahead of
// D34 (trails as connectors) so a future cross-dig match is an explainable shared tag,
// rather than a fragile embedding-similarity coincidence.
export const TRAIL_PATTERNS = [
  'Function Creep', 'Teaching to the Test', 'Moral Hazard', 'Survivorship Bias',
  'Selection Bias', 'Network Effect', 'Tragedy of the Commons', 'Externality',
  'Principal-Agent Problem', 'Regulatory Capture', 'Path Dependency', 'Threshold Effect',
  'Feedback Loop', 'Diminishing Returns', 'Winner-Take-All Dynamics',
  'Information Asymmetry', 'Signal vs. Noise', 'Compounding', 'Bottleneck',
  'Redundancy vs. Fragility', 'Lock-In', 'Free-Rider Problem',
  'Diffusion of Responsibility', 'Margin of Error', 'Emergent Complexity',
] as const;
export type TrailPattern = (typeof TRAIL_PATTERNS)[number];

export interface TrailCandidate {
  move: 'tension' | 'mechanism' | 'precedent' | 'frame' | 'stakes' | 'hidden' | 'scale' | 'unknowns';
  dimension: 'semantic' | 'experiential' | 'social';
  /** The structural pattern this trail's question is an instance of — see TRAIL_PATTERNS. */
  pattern: TrailPattern;
  /** A short, trail-specific phrase (4-8 words) shown as the badge instead of `move` — the
   *  raw category name undersold the actual question. `move`/`dimension` still drive the
   *  diversity selection in pipeline.py's pick(); this is display-only. */
  angle: string;
  question: string;
  hook: string;
  rank: number | null; // 1–4 shown, null = in the remaining 4 behind "More trails"
  /** Real per-trail resources from the Deeper pipeline — absent on hidden ("more") trails
   *  and on older History entries saved before this existed. Preview's MOCK_DIG never sets
   *  this; its rendering falls back to MOCK_DEEPER's lookup-by-move instead (see review.ts). */
  deeper?: DeeperResource[];
}

export interface HeadlineDig {
  sourceUrl: string;
  sourceDomain: string;
  headline: string;
  claim: string;
  what_happened: string;
  why_now: string;
  established: string[];
  contested: ContestedEntry[];
  left_out: string;
  still_unknown: string[];
  sources: { title: string; url: string }[];
  trails: TrailCandidate[];
  explorerCount: number;
}

export const MOCK_DIG: HeadlineDig = {
  sourceUrl:
    'https://www.washingtonpost.com/politics/2026/09/25/government-can-use-social-security-data-identify-noncitizen-voters-supreme-court-rules/',
  sourceDomain: 'washingtonpost.com',
  headline: 'Government can use Social Security data to identify noncitizen voters, Supreme Court rules',
  claim:
    'The Supreme Court ruled that the federal government may let state election officials use a Social Security-linked database to flag voters they suspect are noncitizens.',
  what_happened:
    'On September 25, 2026, the Supreme Court granted the Trump administration’s emergency request to lift a lower-court injunction, letting states resume using the modified SAVE database — which cross-references Social Security records — to flag voters suspected of being noncitizens, while the underlying lawsuit continues.',
  why_now:
    'The order came via emergency application, about six weeks before the 2026 midterms, after DHS had already run more than 65 million voter records through the modified system across 26 states — until a June injunction paused it. States wanted certainty before finalizing their rolls.',
  established: [
    'SAVE is a roughly 40-year-old federal system originally built to verify immigration status for public-benefits eligibility, not voting.',
    'In 2025, DHS overhauled SAVE to link in Social Security Administration records and allow bulk uploads of entire voter rolls instead of individual queries.',
    "A federal district court judge blocked the modified system in June, ruling it violated the Privacy Act and the Social Security Act's confidentiality provisions.",
    'Independent checks of state SAVE results found substantial error rates: about 21% of the voters Texas flagged, and roughly 81% of the voters Missouri flagged, were later confirmed to be citizens.',
  ],
  contested: [
    {
      held_by: 'The Trump administration and DHS',
      position:
        'Federal law obligates the government to help state election officials verify voter citizenship on request, and the modified SAVE system does that at the scale states need.',
    },
    {
      held_by: "The League of Women Voters, EPIC, and the district court's June ruling",
      position:
        'The expanded system violates the Privacy Act and Social Security Act confidentiality rules and functions as a national voter-purge tool never authorized by Congress.',
    },
    {
      held_by: "Justice Ketanji Brown Jackson's dissent, joined by Justices Sotomayor and Kagan",
      position:
        'The harm from disenfranchising even a few lawful voters outweighs the government’s speculative harm from waiting, and nothing in the Social Security Act authorizes this use of the data.',
    },
  ],
  left_out:
    "The headline doesn't mention this is a temporary emergency-docket stay, not a ruling on the merits — the underlying Privacy Act lawsuit continues in district court. It also omits that independent audits found the tool wrongly flagged large shares of citizens as noncitizens, and that three justices dissented.",
  still_unknown: [
    'Whether the modified SAVE system survives the pending Privacy Act and Social Security Act challenge — that district court case would settle it.',
    "How many eligible citizens could be wrongly flagged nationally before the midterms, since only Texas's and Missouri's error rates have been independently checked so far.",
    "Whether flagged voters get a guaranteed chance to prove citizenship before removal in every state, since the ruling doesn't fix a uniform procedure.",
  ],
  sources: [
    { title: 'The Supreme Court revives a controversial data system for citizenship checks — NPR/OPB', url: 'https://www.opb.org/article/2026/09/25/the-supreme-court-revives-the-controversial-save-data-system/' },
    { title: 'Supreme Court says states can use controversial citizenship data tool for voter audits — CNN', url: 'https://www.cnn.com/2026/09/25/politics/supreme-court-voter-roll-non-citizen-save' },
    { title: 'Supreme Court OKs Use of Social Security Data to Check Voter Rolls — U.S. News', url: 'https://www.usnews.com/news/politics/articles/2026-09-25/supreme-court-oks-use-of-social-security-data-to-check-voter-rolls-what-it-means-for-the-midterms' },
    { title: 'Supreme Court revives DHS use of flawed immigration database for voter purges — Democracy Docket', url: 'https://www.democracydocket.com/news-alerts/supreme-court-revives-dhs-use-of-flawed-immigration-database-for-voter-purges/' },
    { title: 'Supreme Court Allows Trump to Use Flawed Database to Vet Voter Citizenship — Mother Jones', url: 'https://www.motherjones.com/politics/2026/09/supreme-court-save-database/' },
  ],
  explorerCount: 128,
  trails: [
    {
      move: 'tension',
      dimension: 'social',
      pattern: 'Function Creep',
      angle: 'A benefits database repurposed for elections',
      question: 'Why would a system built to check eligibility for public benefits end up deciding who gets to vote?',
      hook: 'SAVE was created in the 1980s to verify immigration status for benefits, not elections.',
      rank: 1,
    },
    {
      move: 'mechanism',
      dimension: 'semantic',
      pattern: 'Selection Bias',
      angle: 'How a database mismatch actually happens',
      question: 'How does matching someone’s name against a citizenship database actually produce a false positive?',
      hook: 'Missouri found about 81% of the people SAVE flagged as noncitizens were citizens once cross-checked against passport records.',
      rank: 2,
    },
    {
      move: 'stakes',
      dimension: 'experiential',
      pattern: 'Externality',
      angle: 'Being wrongly flagged days before an election',
      question: 'What actually happens to a naturalized citizen who gets wrongly flagged right before an election?',
      hook: 'Texas confirmed at least 578 of the 2,724 voters it flagged were citizens, who then had to seek reinstatement.',
      rank: 3,
    },
    {
      move: 'hidden',
      dimension: 'social',
      pattern: 'Diffusion of Responsibility',
      angle: 'Who actually makes the final call',
      question: 'Who actually decides whether a flagged voter gets removed — and can they appeal?',
      hook: 'SAVE only flags a match; county election officials, not a federal agency, decide whether to act on it.',
      rank: 4,
    },
    {
      move: 'precedent',
      dimension: 'semantic',
      pattern: 'Path Dependency',
      angle: 'A history of purges gone wrong',
      question: 'When have past attempts to purge noncitizens from voter rolls using government databases gone wrong before?',
      hook: "Florida's 2012 non-citizen voter purge was abandoned after most flagged voters turned out to be citizens.",
      rank: null,
    },
    {
      move: 'frame',
      dimension: 'social',
      pattern: 'Information Asymmetry',
      angle: 'Two names for the same policy',
      question: "How do 'election integrity' and 'voter suppression' end up describing the exact same policy?",
      hook: 'The administration calls SAVE a verification tool; challengers call it a de facto national purge system.',
      rank: null,
    },
    {
      move: 'scale',
      dimension: 'semantic',
      pattern: 'Margin of Error',
      angle: '28,635 flags against the real number',
      question: 'How does a 28,000-name flag list compare to how many noncitizens are actually estimated to vote?',
      hook: 'SAVE has flagged 28,635 potential noncitizens out of more than 65 million voters checked since May 2025.',
      rank: null,
    },
    {
      move: 'unknowns',
      dimension: 'experiential',
      pattern: 'Signal vs. Noise',
      angle: 'What proof of accuracy would even look like',
      question: 'What would it take to actually know how accurate a citizenship-verification database is before using it nationwide?',
      hook: "No state has published a full independent audit of SAVE's accuracy — only Texas's and Missouri's numbers are public.",
      rank: null,
    },
  ],
};
