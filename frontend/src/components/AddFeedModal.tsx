import { useState, useRef } from 'react';
import { X, Rss, Loader, Upload, Download, Database } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { api } from '../api/client';

export function AddFeedModal() {
  const { setAddFeedModalOpen, addFeed, folders, seedFeeds } = useAppStore();
  
  const [activeTab, setActiveTab] = useState<'add' | 'opml'>('add');
  
  // Add Feed State
  const [url, setUrl] = useState('');
  const [folderId, setFolderId] = useState<number | ''>('');
  const [isAdding, setIsAdding] = useState(false);
  const [addError, setAddError] = useState('');

  // OPML State
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [importResult, setImportResult] = useState<{ feeds: number; folders: number; skipped: number } | null>(null);
  const [opmlError, setOpmlError] = useState('');
  const [isSeeding, setIsSeeding] = useState(false);

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;

    setIsAdding(true);
    setAddError('');

    try {
      await addFeed(url, folderId === '' ? undefined : folderId);
    } catch (err: any) {
      setAddError(err.message || 'Failed to add feed. Please check the URL.');
    } finally {
      setIsAdding(false);
    }
  };

  const handleImportOpml = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsImporting(true);
    setOpmlError('');
    setImportResult(null);

    try {
      const result = await api.importOpml(file);
      await useAppStore.getState().fetchFeeds();
      await useAppStore.getState().fetchArticles(true);
      
      setImportResult({
        feeds: result.imported_feeds,
        folders: result.imported_folders,
        skipped: result.skipped_feeds,
      });
    } catch (err: any) {
      setOpmlError(err.message || 'Failed to import OPML file.');
    } finally {
      setIsImporting(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleSeed = async () => {
    setIsSeeding(true);
    setOpmlError('');
    setImportResult(null);

    try {
      await seedFeeds();
    } catch (err: any) {
      setOpmlError(err.message || 'Failed to seed feeds.');
    } finally {
      setIsSeeding(false);
    }
  };

  const handleExportOpml = () => {
    const link = document.createElement('a');
    link.href = api.exportOpmlUrl();
    link.setAttribute('download', 'feeda-export.opml');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-gray-900 border border-gray-700/50 rounded-lg shadow-xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between p-4 border-b border-gray-700/50">
          <h2 className="text-lg font-semibold text-gray-100 flex items-center gap-2">
            <Rss size={20} className="text-blue-500" />
            Manage Feeds
          </h2>
          <button 
            onClick={() => setAddFeedModalOpen(false)}
            className="text-gray-400 hover:text-gray-200 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex border-b border-gray-800">
          <button
            className={`flex-1 py-3 text-sm font-medium transition-colors ${activeTab === 'add' ? 'text-blue-400 border-b-2 border-blue-500' : 'text-gray-400 hover:text-gray-200'}`}
            onClick={() => setActiveTab('add')}
          >
            Add Single Feed
          </button>
          <button
            className={`flex-1 py-3 text-sm font-medium transition-colors ${activeTab === 'opml' ? 'text-blue-400 border-b-2 border-blue-500' : 'text-gray-400 hover:text-gray-200'}`}
            onClick={() => setActiveTab('opml')}
          >
            Import / Export
          </button>
        </div>

        {activeTab === 'add' ? (
          <form onSubmit={handleAddSubmit} className="p-4 space-y-4">
            <div>
              <label htmlFor="feed-url" className="block text-sm font-medium text-gray-300 mb-1">
                RSS/Atom Feed URL
              </label>
              <input
                id="feed-url"
                type="url"
                placeholder="https://example.com/feed.xml"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                required
                className="w-full bg-gray-950 border border-gray-700 rounded-md px-3 py-2 text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              />
            </div>

            <div>
              <label htmlFor="folder-select" className="block text-sm font-medium text-gray-300 mb-1">
                Folder (Optional)
              </label>
              <select
                id="folder-select"
                value={folderId}
                onChange={(e) => setFolderId(e.target.value ? Number(e.target.value) : '')}
                className="w-full bg-gray-950 border border-gray-700 rounded-md px-3 py-2 text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              >
                <option value="">-- No Folder --</option>
                {folders.map(f => (
                  <option key={f.id} value={f.id}>{f.name}</option>
                ))}
              </select>
            </div>

            {addError && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-md text-red-500 text-sm">
                {addError}
              </div>
            )}

            <div className="pt-4 flex justify-end gap-3 border-t border-gray-800">
              <button
                type="button"
                onClick={() => setAddFeedModalOpen(false)}
                className="px-4 py-2 text-sm font-medium text-gray-300 hover:text-gray-100 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isAdding || !url}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-600/50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-md transition-colors flex items-center gap-2"
              >
                {isAdding ? (
                  <>
                    <Loader size={16} className="animate-spin" />
                    Adding...
                  </>
                ) : 'Add Feed'}
              </button>
            </div>
          </form>
        ) : (
          <div className="p-4 space-y-6">
            <div>
              <h3 className="text-sm font-medium text-gray-300 mb-2">Import Subscriptions</h3>
              <p className="text-xs text-gray-400 mb-3">Upload an OPML file exported from Feedly, Inoreader, or other RSS readers.</p>
              
              <input 
                type="file" 
                accept=".opml,.xml" 
                ref={fileInputRef} 
                onChange={handleImportOpml} 
                className="hidden" 
              />
              
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isImporting || isSeeding}
                className="w-full py-2 bg-gray-800 hover:bg-gray-700 disabled:bg-gray-800/50 text-gray-200 text-sm font-medium rounded-md border border-gray-700 transition-colors flex items-center justify-center gap-2"
              >
                {isImporting ? <Loader size={16} className="animate-spin" /> : <Upload size={16} />}
                {isImporting ? 'Importing...' : 'Import OPML'}
              </button>
            </div>

            <div>
              <h3 className="text-sm font-medium text-gray-300 mb-2">Export Subscriptions</h3>
              <p className="text-xs text-gray-400 mb-3">Download your current Feeda subscriptions as an OPML file.</p>
              
              <button
                onClick={handleExportOpml}
                className="w-full py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 text-sm font-medium rounded-md border border-gray-700 transition-colors flex items-center justify-center gap-2"
              >
                <Download size={16} />
                Export OPML
              </button>
            </div>

            <div className="pt-4 border-t border-gray-800">
              <h3 className="text-sm font-medium text-gray-300 mb-2">Restore Default Data</h3>
              <p className="text-xs text-gray-400 mb-3">Pre-populate Feeda with standard folders and popular feeds.</p>
              
              <button
                onClick={handleSeed}
                disabled={isImporting || isSeeding}
                className="w-full py-2 bg-blue-900/30 hover:bg-blue-800/40 text-blue-400 text-sm font-medium rounded-md border border-blue-900/50 transition-colors flex items-center justify-center gap-2"
              >
                {isSeeding ? <Loader size={16} className="animate-spin" /> : <Database size={16} />}
                {isSeeding ? 'Seeding...' : 'Restore Screenshot Feeds'}
              </button>
            </div>

            {opmlError && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-md text-red-500 text-sm">
                {opmlError}
              </div>
            )}

            {importResult && (
              <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-md text-green-400 text-sm">
                Successfully imported {importResult.feeds} feeds across {importResult.folders} folders ({importResult.skipped} existing skipped)
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
