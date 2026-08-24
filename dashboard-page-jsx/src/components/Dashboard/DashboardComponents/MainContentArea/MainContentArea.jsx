import React from 'react';
import WelcomeBanner from './WelcomeBanner/WelcomeBanner';
import StatsCards from './StatsCards/StatsCards';
import RecentActivity from './RecentActivity/RecentActivity';
import NotificationsPanel from './NotificationsPanel/NotificationsPanel';
function MainContentArea() {
  return (
    <div className="flex-1 p-4">
      <WelcomeBanner />
      <StatsCards />
      <RecentActivity />
      <NotificationsPanel />
    </div>
  );
}
export default MainContentArea;