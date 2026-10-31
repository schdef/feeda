import { useState, useEffect } from 'react';
import { Search } from 'lucide-react';
import { useAppStore } from '../stores/appStore';

export function SearchBar() {
  const { searchQuery, setSearchQuery } = useAppStore();
  const [localQuery, setLocalQuery] = useState(searchQuery);

  // Simple debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchQuery(localQuery);
    }, 300);

    return () => clearTimeout(timer);
  }, [localQuery, setSearchQuery]);

  return (
    <div className="relative">
      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
        <Search size={16} className="text-gray-500" />
      </div>
      <input
        id="search-input"
        type="text"
        placeholder="Search articles... (/)"
        value={localQuery}
        onChange={(e) => setLocalQuery(e.target.value)}
        className="block w-full pl-9 pr-3 py-1.5 bg-gray-950 border border-gray-700/50 rounded-md text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 transition-colors"
      />
    </div>
  );
}
