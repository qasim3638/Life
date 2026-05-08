import React from 'react';
import { DocumentForm } from '../../components/documents/DocumentForm';

/**
 * Refund Page - Uses shared DocumentForm component
 */
export const Refund = () => {
  return <DocumentForm documentType="refund" />;
};

export default Refund;
