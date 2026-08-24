import { useState } from 'react';
function useTopHeaderBar() {
  const [user, setUser] = useState({ name: 'Alex Johnson' });
  return { user };
}
export default useTopHeaderBar;