# Mangus — App Store submission kit

Everything to fill in App Store Connect. Copy/paste as needed.

## App identity
- **Bundle ID:** `com.walkap.mangus`
- **App Name (30 char max):** `Mangus: Chess Coach`
  - If taken, try: `Mangus Chess Coach` or `Mangus — Chess Review`
- **Subtitle (30 char max):** `Your chess.com games, coached`
- **Primary category:** Games (Board) · **Secondary:** Education
- **Age rating:** 4+ (no objectionable content)
- **Price:** Free

## Promotional text (170 char max, editable anytime without review)
> Type your chess.com username and get every game analyzed on your phone —
> move-by-move verdicts, the best move at any position, and why you actually lost.

## Description
> Mangus turns your chess.com games into a coach. Type your username and it pulls
> your recent games and analyzes every move with Stockfish — right on your phone,
> no account and no servers.
>
> • Every move graded — best, inaccuracy, mistake, blunder — with the win% it cost.
> • Tap "Show best move" at any position to see what you should have played.
> • Understand why you lost each game: the one move that actually decided it.
> • Spot your patterns across games — hung pieces, allowed tactics, and where your
>   blunders tend to happen.
> • Per-game accuracy, and an estimate of how strong you played.
>
> Everything runs on your device. No login, no ads, no tracking. Just your games,
> coached.

## Keywords (100 char max, comma-separated, no spaces)
```
chess,coach,analysis,chess.com,blunder,tactics,game review,improve,stockfish,rating,study
```

## URLs
- **Support URL:** https://walkap123.github.io/mangus/support.html
- **Privacy Policy URL:** https://walkap123.github.io/mangus/privacy.html
- **Marketing URL:** (optional — leave blank)

  > These go live once GitHub Pages is enabled on the mangus repo (Settings →
  > Pages → Deploy from branch: `main`, folder `/docs`). Then the URLs above work.

## App Privacy (the questionnaire)
Answer: **Data Not Collected.**
- Mangus has no server and no accounts. Nothing is transmitted to the developer.
- The only network call is to chess.com's **public** API to download the games
  for a username the user types — real-time app functionality, not collection.
- The username is stored **only on the device** (to prefill next launch).
- No analytics, no ads, no third-party SDKs, no tracking.

## Export compliance
- Uses only standard encryption (HTTPS). Already declared in the build via
  `ITSAppUsesNonExemptEncryption = false`, so no extra questions.

## Review notes (IMPORTANT — tell the reviewer how to test)
> Mangus needs no login. To test: on the home screen, type a chess.com username
> (for example: hikaru) and tap "Analyze my games." The app downloads that
> player's public games from chess.com and analyzes them on-device (takes ~1–2
> minutes on first run). Then browse the games and tap into any one to review it.
> Requires an internet connection to download games.

## Screenshots (you pulled these — sizes Apple requires)
- **Required:** 6.9"/6.7" iPhone — **1290 × 2796** (portrait). At least 1, up to 10.
- Older 6.5" (1284 × 2778) optional. iPad only if you enable iPad support.
- Good ones to include: the games list (with the recent-game board + accuracy/ELO
  bubbles), a game review with a move verdict, "Show best move" with the arrows,
  and the Patterns tab.

## Copyright
`2026 Walker Pate` (or your preferred name)

## Submission order
1. `eas build --profile production --platform ios --auto-submit` (build + upload).
2. In App Store Connect: create the app (bundle `com.walkap.mangus`), fill the
   fields above, upload screenshots, set price = Free.
3. Answer App Privacy = Data Not Collected.
4. Select the uploaded build, add the review notes, Submit for Review.
