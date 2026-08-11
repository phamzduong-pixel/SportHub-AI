import { useCallback, useState } from 'react';

export function useDisclosure(initial = false) {
  const [isOpen, setIsOpen] = useState(initial);
  return { isOpen, open: useCallback(() => setIsOpen(true), []), close: useCallback(() => setIsOpen(false), []), toggle: useCallback(() => setIsOpen((value) => !value), []) };
}
