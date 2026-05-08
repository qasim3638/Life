/**
 * BlogArticlePage — /blog/:slug
 *
 * Renders a published article from the Editorial Autopilot.
 * - Markdown rendered via react-markdown
 * - JSON-LD Article schema injected via the Express SSR layer at
 *   request time (so it's visible to Google before JS executes)
 * - FAQ block rendered as native HTML for accessibility + bonus
 *   FAQPage rich-result eligibility
 * - Internal links and related products injected into the body
 */
import React, { useEffect, useState } from 'react';
import { useParams, Link, Navigate } from 'react-router-dom';
import { Loader2, Calendar, ArrowLeft } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { ShopHeader, ShopFooter } from './TileStationHome';
import { BreadcrumbSchema } from '../../components/seo/StructuredData';
import SeoHead from '../../components/seo/SeoHead';

const API_URL = process.env.REACT_APP_BACKEND_URL;


const BlogArticlePage = () => {
  const { slug } = useParams();
  const [article, setArticle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setNotFound(false);
    fetch(`${API_URL}/api/shop/blog/${slug}`)
      .then((r) => {
        if (r.status === 404) { setNotFound(true); return null; }
        return r.json();
      })
      .then((d) => { if (alive && d) setArticle(d); })
      .catch(() => { if (alive) setNotFound(true); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [slug]);

  if (notFound) return <Navigate to="/blog" replace />;

  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-stone-400" />
      </div>
    );
  }

  if (!article) return null;

  const heroSrc = article.hero_image_url ? `${API_URL}${article.hero_image_url}` : null;
  const publishedDate = article.published_at ? new Date(article.published_at) : null;

  return (
    <div className="min-h-screen bg-white" data-testid="blog-article-page">
      <SeoHead
        title={`${article.title} · TileStation`}
        description={article.meta_description}
        canonical={`/blog/${article.slug}`}
        ogImage={heroSrc || undefined}
      />
      <BreadcrumbSchema
        items={[
          { name: 'Home', url: '/' },
          { name: 'Blog', url: '/blog' },
          { name: article.title, url: `/blog/${article.slug}` },
        ]}
      />
      <ShopHeader />

      <article className="max-w-3xl mx-auto px-4 py-8 md:py-12">
        <Link
          to="/blog"
          className="inline-flex items-center gap-1 text-xs text-stone-500 hover:text-amber-700 font-semibold mb-6"
          data-testid="blog-article-back-link"
        >
          <ArrowLeft className="w-3 h-3" /> All articles
        </Link>

        <h1
          className="text-3xl md:text-5xl font-bold text-stone-900 leading-tight mb-4"
          data-testid="blog-article-title"
        >
          {article.title}
        </h1>

        {publishedDate && (
          <div className="flex items-center gap-2 text-sm text-stone-500 mb-8">
            <Calendar className="w-4 h-4" />
            <time dateTime={publishedDate.toISOString()}>
              {publishedDate.toLocaleDateString('en-GB', {
                day: 'numeric', month: 'long', year: 'numeric',
              })}
            </time>
          </div>
        )}

        {heroSrc && (
          <div className="aspect-[16/9] bg-stone-100 rounded-xl overflow-hidden mb-8 md:mb-10">
            <img src={heroSrc} alt={article.title} className="w-full h-full object-cover" />
          </div>
        )}

        <div
          className="prose prose-stone max-w-none prose-headings:font-bold prose-h2:text-2xl prose-h2:mt-10 prose-h3:text-xl prose-a:text-amber-700 hover:prose-a:text-amber-900 prose-img:rounded-lg"
          data-testid="blog-article-body"
        >
          <ReactMarkdown>{article.body_md || ''}</ReactMarkdown>
        </div>

        {Array.isArray(article.faqs) && article.faqs.length > 0 && (
          <section className="mt-12 pt-8 border-t border-stone-200" data-testid="blog-article-faqs">
            <h2 className="text-2xl font-bold text-stone-900 mb-6">Frequently asked</h2>
            <div className="space-y-5">
              {article.faqs.map((f, i) => (
                <div key={i}>
                  <h3 className="text-base font-semibold text-stone-900">{f.q}</h3>
                  <p className="text-sm text-stone-700 mt-1.5 leading-relaxed">{f.a}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        {Array.isArray(article.internal_links) && article.internal_links.length > 0 && (
          <section className="mt-12 pt-8 border-t border-stone-200" data-testid="blog-article-internal-links">
            <h2 className="text-base font-bold text-stone-900 uppercase tracking-wider mb-4">Explore TileStation</h2>
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {article.internal_links.map((link, i) => (
                <li key={i}>
                  <Link
                    to={link.url}
                    className="block px-4 py-3 rounded-lg bg-stone-50 hover:bg-amber-50 border border-stone-200 hover:border-amber-300 text-sm font-semibold text-stone-800 hover:text-amber-800 transition"
                  >
                    {link.anchor} →
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* FAQ JSON-LD for Google rich-results — non-visual */}
        {Array.isArray(article.faqs) && article.faqs.length > 0 && (
          <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{
              __html: JSON.stringify({
                '@context': 'https://schema.org',
                '@type': 'FAQPage',
                mainEntity: article.faqs.map((f) => ({
                  '@type': 'Question',
                  name: f.q,
                  acceptedAnswer: { '@type': 'Answer', text: f.a },
                })),
              }),
            }}
          />
        )}
      </article>

      <ShopFooter />
    </div>
  );
};

export default BlogArticlePage;
