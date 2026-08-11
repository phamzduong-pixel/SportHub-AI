import { CalendarDays, Clock3, MapPin, Search } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Input, Select } from '@/components/common';

interface Props { compact?: boolean; initialQuery?: string; }
export function VenueSearchBar({ compact = false, initialQuery = '' }: Props) {
  const navigate = useNavigate();
  const [location, setLocation] = useState(initialQuery);
  const [sport, setSport] = useState('');
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const params = new URLSearchParams();
    if (location) params.set('q', location);
    if (sport) params.set('sport', sport);
    if (date) params.set('date', date);
    if (time) params.set('time', time);
    navigate(`/venues?${params.toString()}`);
  };
  return <form onSubmit={submit} className={`grid gap-3 ${compact ? 'md:grid-cols-[1.3fr_1fr_1fr_1fr_auto]' : 'lg:grid-cols-[1.35fr_1fr_1fr_1fr_auto]'}`}>
    <Input aria-label="Địa điểm" value={location} onChange={(event) => setLocation(event.target.value)} leftIcon={<MapPin size={17} />} placeholder="Quận, thành phố..." />
    <Select aria-label="Môn thể thao" value={sport} onChange={(event) => setSport(event.target.value)} options={['Bóng đá', 'Cầu lông', 'Pickleball', 'Tennis', 'Bóng rổ', 'Bóng chuyền'].map((item) => ({ label: item, value: item }))} placeholder="Môn thể thao" />
    <Input aria-label="Ngày chơi" type="date" value={date} onChange={(event) => setDate(event.target.value)} leftIcon={<CalendarDays size={17} />} />
    <Select aria-label="Khung giờ" value={time} onChange={(event) => setTime(event.target.value)} options={['Sáng (05:00–11:00)', 'Trưa (11:00–14:00)', 'Chiều (14:00–18:00)', 'Tối (18:00–23:00)'].map((item) => ({ label: item, value: item }))} placeholder="Khung giờ" />
    <Button type="submit" size={compact ? 'md' : 'lg'} leftIcon={<Search size={18} />} className="w-full">Tìm sân</Button>
    {!compact && <span className="sr-only"><Clock3 />Chọn thời gian chơi mong muốn</span>}
  </form>;
}
