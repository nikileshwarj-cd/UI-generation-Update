import React from 'react';
import TotalProjects from './TotalProjects/TotalProjects';
import PendingTasks from './PendingTasks/PendingTasks';
import CompletedTasks from './CompletedTasks/CompletedTasks';
import Notifications from './Notifications/Notifications';
function StatsCards() {
  return (
    <div className="stats-cards">
      <TotalProjects />
      <PendingTasks />
      <CompletedTasks />
      <Notifications />
    </div>
  );
}
export default StatsCards;