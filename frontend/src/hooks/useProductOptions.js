import { useState, useEffect, useCallback } from 'react';
import { api } from '../lib/api';

export const useProductOptions = () => {
  const [options, setOptions] = useState({
    materials: [],
    types: [],
    finishes: [],
    edges: [],
    slip_ratings: [],
    suitabilities: [],
    thicknesses: [],
    countries: [],  // Country of Origin options
    styles: [],
    features: [],
    rooms: [],
    colors: [],
    main_categories: [],
    sub_categories: []
  });
  const [loading, setLoading] = useState(true);

  const fetchOptions = useCallback(async () => {
    try {
      setLoading(true);
      
      // Fetch from BOTH sources and merge them
      const [legacyResponse, unifiedResponse] = await Promise.all([
        api.get('/supplier-sync/website-category-options').catch(() => ({ data: {} })),
        api.get('/filters/bulk-editor-options').catch(() => ({ data: {} }))
      ]);
      
      const legacyData = legacyResponse?.data || legacyResponse || {};
      const unifiedData = unifiedResponse?.data || unifiedResponse || {};
      
      // Helper function to merge options arrays, avoiding duplicates
      const mergeOptions = (legacy = [], unified = []) => {
        const seen = new Set();
        const merged = [];
        
        // Add legacy options first
        for (const opt of legacy) {
          const id = opt.id || opt.value;
          if (id && !seen.has(id)) {
            seen.add(id);
            merged.push(opt);
          }
        }
        
        // Add unified options that aren't already present
        for (const opt of unified) {
          const id = opt.id || opt.value;
          if (id && !seen.has(id)) {
            seen.add(id);
            merged.push(opt);
          }
        }
        
        return merged;
      };
      
      // Build merged options
      const newOptions = {
        materials: mergeOptions(legacyData.materials, unifiedData.material),
        types: mergeOptions(legacyData.types, unifiedData.types),
        finishes: mergeOptions(legacyData.finishes, unifiedData.finish),
        edges: mergeOptions(legacyData.edges, unifiedData.edge),
        slip_ratings: mergeOptions(legacyData.slip_ratings, unifiedData.slip_rating),
        suitabilities: mergeOptions(legacyData.suitabilities, unifiedData.suitability),
        thicknesses: mergeOptions(legacyData.thicknesses, unifiedData.thickness),
        countries: mergeOptions(legacyData.countries, unifiedData.country_of_origin),
        styles: mergeOptions(legacyData.styles, unifiedData.style),
        features: mergeOptions(legacyData.features, unifiedData.features),
        rooms: mergeOptions(legacyData.rooms, unifiedData.room),
        colors: mergeOptions(legacyData.colors, unifiedData.color),
        main_categories: legacyData.main_categories || [],
        sub_categories: legacyData.sub_categories || []
      };
      
      // Also include any custom categories from legacy (like "flooring", "applications", etc.)
      Object.keys(legacyData).forEach(key => {
        if (!newOptions[key] && Array.isArray(legacyData[key])) {
          newOptions[key] = legacyData[key];
        }
      });
      
      setOptions(newOptions);
    } catch (error) {
      console.error('Error fetching product options:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOptions();
  }, [fetchOptions]);

  const addOption = useCallback(async (category, value) => {
    try {
      // Map category names to filter slugs
      const categoryToFilterSlug = {
        'materials': 'material',
        'finishes': 'finish',
        'edges': 'edge',
        'slip_ratings': 'slip-rating',
        'suitabilities': 'suitability',
        'thicknesses': 'thickness',
        'countries': 'country-of-origin',
        'styles': 'style',
        'features': 'features',
        'rooms': 'room',
        'colors': 'color'
      };
      
      const filterSlug = categoryToFilterSlug[category];
      const valueId = value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      
      // Add to legacy system
      const legacyResponse = await api.post('/supplier-sync/website-category-options', {
        category_type: category,
        id: valueId.replace(/-/g, '_'),
        label: value,
        color: 'bg-gray-500'
      }).catch(e => ({ data: { success: false } }));
      
      // Also add to unified filter_types system
      if (filterSlug) {
        try {
          await api.post(`/filters/types/${filterSlug}/add-value`, {
            value: valueId,
            label: value,
            is_active: true
          });
        } catch (e) {
          console.log('Could not add to filter_types (may not exist yet)');
        }
      }
      
      const data = legacyResponse?.data || legacyResponse;
      if (data.success || data.id) {
        // Refresh options
        await fetchOptions();
        return true;
      }
      return false;
    } catch (error) {
      console.error('Error adding option:', error);
      return false;
    }
  }, [fetchOptions]);

  const updateOption = useCallback(async (category, oldValue, newValue) => {
    try {
      // Convert the label to option ID format (same as backend expects)
      const optionId = oldValue.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
      
      const response = await api.put(
        `/supplier-sync/website-category-options/${encodeURIComponent(category)}/${encodeURIComponent(optionId)}`,
        { label: newValue }
      );
      const data = response?.data || response;
      if (data.success) {
        // Refresh options WITHOUT setting loading state
        try {
          const refreshResponse = await api.get('/supplier-sync/website-category-options');
          const refreshData = refreshResponse?.data || refreshResponse;
          if (refreshData) {
            const newOptions = {
              materials: refreshData.materials || [],
              types: refreshData.types || [],
              finishes: refreshData.finishes || [],
              edges: refreshData.edges || [],
              slip_ratings: refreshData.slip_ratings || [],
              suitabilities: refreshData.suitabilities || [],
              thicknesses: refreshData.thicknesses || [],
              countries: refreshData.countries || [],
              styles: refreshData.styles || [],
              features: refreshData.features || [],
              rooms: refreshData.rooms || [],
              colors: refreshData.colors || [],
              main_categories: refreshData.main_categories || [],
              sub_categories: refreshData.sub_categories || []
            };
            Object.keys(refreshData).forEach(key => {
              if (!newOptions[key] && Array.isArray(refreshData[key])) {
                newOptions[key] = refreshData[key];
              }
            });
            setOptions(newOptions);
          }
        } catch (refreshError) {
          console.error('Error refreshing options:', refreshError);
        }
        return true;
      }
      return false;
    } catch (error) {
      console.error('Error updating option:', error);
      return false;
    }
  }, []);

  const deleteOption = useCallback(async (category, value) => {
    try {
      // Map category names to filter slugs
      const categoryToFilterSlug = {
        'materials': 'material',
        'finishes': 'finish',
        'edges': 'edge',
        'slip_ratings': 'slip-rating',
        'suitabilities': 'suitability',
        'thicknesses': 'thickness',
        'countries': 'country-of-origin',
        'styles': 'style',
        'features': 'features',
        'rooms': 'room',
        'colors': 'color'
      };
      
      // Get the option ID - convert label to ID format
      // Replace spaces, special characters with underscores
      const optionId = value.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
      const filterSlug = categoryToFilterSlug[category];
      
      // Delete from legacy system
      const response = await api.delete(`/supplier-sync/website-category-options/${encodeURIComponent(category)}/${encodeURIComponent(optionId)}`);
      const data = response?.data || response;
      
      // Also delete from unified filter_types system (if it exists there)
      if (filterSlug) {
        try {
          const valueId = value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
          await api.delete(`/filters/types/by-slug/${filterSlug}/values/${valueId}`);
        } catch (e) {
          console.log('Could not delete from filter_types (may not exist or different format)');
        }
      }
      
      if (data.success) {
        // Fetch options WITHOUT setting loading state to avoid the spinner issue
        try {
          const refreshResponse = await api.get('/supplier-sync/website-category-options');
          const refreshData = refreshResponse?.data || refreshResponse;
          if (refreshData) {
            const newOptions = {
              materials: refreshData.materials || [],
              types: refreshData.types || [],
              finishes: refreshData.finishes || [],
              edges: refreshData.edges || [],
              slip_ratings: refreshData.slip_ratings || [],
              suitabilities: refreshData.suitabilities || [],
              thicknesses: refreshData.thicknesses || [],
              countries: refreshData.countries || [],
              styles: refreshData.styles || [],
              features: refreshData.features || [],
              rooms: refreshData.rooms || [],
              colors: refreshData.colors || [],
              main_categories: refreshData.main_categories || [],
              sub_categories: refreshData.sub_categories || []
            };
            Object.keys(refreshData).forEach(key => {
              if (!newOptions[key] && Array.isArray(refreshData[key])) {
                newOptions[key] = refreshData[key];
              }
            });
            setOptions(newOptions);
          }
        } catch (refreshError) {
          console.error('Error refreshing options:', refreshError);
        }
        return true;
      }
      return false;
    } catch (error) {
      console.error('Error deleting option:', error);
      return false;
    }
  }, []);

  return {
    options,
    loading,
    fetchOptions,
    addOption,
    updateOption,
    deleteOption
  };
};

export default useProductOptions;
