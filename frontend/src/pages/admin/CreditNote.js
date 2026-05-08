import React from 'react';
import { DocumentForm } from '../../components/documents/DocumentForm';

/**
 * Credit Note Page - Uses shared DocumentForm component
 */
export const CreditNote = () => {
  return <DocumentForm documentType="creditNote" />;
};

export default CreditNote;
