import { useState } from 'react';
function useSidebar() {
  const [activeLink, setActiveLink] = useState('Dashboard');
  return { activeLink, setActiveLink };
}
export default useSidebar;