export const sportImages = {
  football: '/images/sports/football-court.webp',
  badminton: '/images/sports/badminton-court.webp',
  tennis: '/images/sports/tennis-court.webp',
  basketball: '/images/sports/basketball-court.webp',
  pickleball: '/images/sports/pickleball-court.webp',
  volleyball: '/images/sports/volleyball-court.webp',
} as const;

const normalizeSport = (sport?: string | null) => (sport || '')
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .replace(/đ/g, 'd')
  .toLowerCase()
  .trim();

export function getSportImage(sport?: string | null): string {
  const value = normalizeSport(sport);
  if (value.includes('pickleball')) return sportImages.pickleball;
  if (value.includes('cau long') || value.includes('badminton')) return sportImages.badminton;
  if (value.includes('bong ro') || value.includes('basketball')) return sportImages.basketball;
  if (value.includes('bong chuyen') || value.includes('volleyball')) return sportImages.volleyball;
  if (value.includes('tennis') || value.includes('quan vot')) return sportImages.tennis;
  return sportImages.football;
}
