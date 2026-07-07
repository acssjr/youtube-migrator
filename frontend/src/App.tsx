import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DashboardLayout } from './layouts/DashboardLayout';
import { MigrationPage } from './pages/MigrationPage';
import { SettingsPage } from './pages/SettingsPage';
import { LogsPage } from './pages/LogsPage';

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
  const [activeTab, setActiveTab] = useState<string>('migration');

  return (
    <QueryClientProvider client={queryClient}>
      <DashboardLayout activeTab={activeTab} setActiveTab={setActiveTab}>
        {activeTab === 'migration' && <MigrationPage />}
        {activeTab === 'settings' && <SettingsPage />}
        {activeTab === 'logs' && <LogsPage />}
      </DashboardLayout>
    </QueryClientProvider>
  );
}
