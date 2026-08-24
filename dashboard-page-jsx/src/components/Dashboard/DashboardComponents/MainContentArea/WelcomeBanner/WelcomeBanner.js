import { useState } from 'react';
function useWelcomeBanner() {
  const [user, setUser] = useState({ name: 'Alex Johnson' });
  return { user };
}
export default useWelcomeBanner;