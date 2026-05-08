import React, { useState } from 'react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../components/ui/tabs';
import { Image, GitMerge, Settings, Sliders } from 'lucide-react';
import CollectionManager from './CollectionManager';
import CollectionMappingManager from './CollectionMappingManager';
import CollectionsPageSettings from './CollectionsPageSettings';
import CollectionDetailSettings from './CollectionDetailSettings';

export default function CollectionsHub() {
  const [activeTab, setActiveTab] = useState('manager');

  return (
    <div className="h-full flex flex-col" data-testid="collections-hub">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b bg-white">
        <h1 className="text-2xl font-bold text-gray-900">Collections</h1>
        <p className="text-gray-500 mt-1">Manage images, mappings, page content, and detail page settings</p>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-4">
          <TabsList className="bg-gray-100 p-1 h-auto">
            <TabsTrigger
              value="manager"
              className="flex items-center gap-2 px-4 py-2 text-sm data-[state=active]:bg-white data-[state=active]:shadow-sm"
              data-testid="tab-collection-manager"
            >
              <Image className="w-4 h-4" />
              Collection Manager
            </TabsTrigger>
            <TabsTrigger
              value="mapping"
              className="flex items-center gap-2 px-4 py-2 text-sm data-[state=active]:bg-white data-[state=active]:shadow-sm"
              data-testid="tab-collection-mapping"
            >
              <GitMerge className="w-4 h-4" />
              Collection Mapping
            </TabsTrigger>
            <TabsTrigger
              value="page-settings"
              className="flex items-center gap-2 px-4 py-2 text-sm data-[state=active]:bg-white data-[state=active]:shadow-sm"
              data-testid="tab-page-settings"
            >
              <Settings className="w-4 h-4" />
              Page Settings
            </TabsTrigger>
            <TabsTrigger
              value="detail-settings"
              className="flex items-center gap-2 px-4 py-2 text-sm data-[state=active]:bg-white data-[state=active]:shadow-sm"
              data-testid="tab-detail-settings"
            >
              <Sliders className="w-4 h-4" />
              Detail Page
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto">
        {activeTab === 'manager' && <CollectionManager embedded />}
        {activeTab === 'mapping' && <CollectionMappingManager embedded />}
        {activeTab === 'page-settings' && <CollectionsPageSettings embedded />}
        {activeTab === 'detail-settings' && <CollectionDetailSettings embedded />}
      </div>
    </div>
  );
}
