import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DashboardLayout } from './layouts/DashboardLayout';
import { MigrationPage } from './pages/MigrationPage';
import { SettingsPage } from './pages/SettingsPage';
import { LogsPage } from './pages/LogsPage';
import { DescriptionsPage } from './pages/DescriptionsPage';
import { DownloadsPage } from './pages/DownloadsPage';

// Create TanStack Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export default function App() {
  const [activeTab, setActiveTab] = useState<string>(window.location.pathname === '/settings' || new URLSearchParams(window.location.search).has('auth') ? 'settings' : window.location.pathname === '/downloads' ? 'downloads' : 'descriptions');

  return (
    <QueryClientProvider client={queryClient}>
      <DashboardLayout activeTab={activeTab} setActiveTab={setActiveTab}>
        {activeTab === 'descriptions' && <DescriptionsPage />}
        {activeTab === 'downloads' && <DownloadsPage />}
        {activeTab === 'migration' && <MigrationPage />}
        {activeTab === 'settings' && <SettingsPage />}
        {activeTab === 'logs' && <LogsPage />}
      </DashboardLayout>
    </QueryClientProvider>
  );
}
