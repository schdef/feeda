import { useEffect } from 'react';
import { Layout } from './components/Layout';
import { Sidebar } from './components/Sidebar';
import { ArticleList } from './components/ArticleList';
import { ArticleReader } from './components/ArticleReader';
import { DiscoverView } from './components/DiscoverView';
import { useAppStore } from './stores/appStore';
import { useKeyboard } from './hooks/useKeyboard';

function App() {
  const { fetchFeeds, fetchArticles, setOffline, syncOfflineActions, discoverViewOpen } = useAppStore();
  
  useKeyboard();

  useEffect(() => {
    fetchFeeds();
    fetchArticles(true);

    const handleOnline = () => {
      setOffline(false);
      syncOfflineActions();
      fetchFeeds();
      fetchArticles(true);
    };

    const handleOffline = () => {
      setOffline(true);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [fetchFeeds, fetchArticles, setOffline, syncOfflineActions]);

  return (
    <Layout
      sidebar={<Sidebar />}
      articleList={discoverViewOpen ? <DiscoverView /> : <ArticleList />}
      articleReader={<ArticleReader />}
    />
  );
}

export default App;
