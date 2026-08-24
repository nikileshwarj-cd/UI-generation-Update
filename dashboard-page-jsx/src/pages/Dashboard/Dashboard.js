import { useState } from 'react';
function useDashboardPage() {
  const [user, setUser] = useState({ name: 'Alex Johnson' });
  return { user };
}
export default useDashboardPage;