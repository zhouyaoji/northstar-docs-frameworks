const config = {
  title: 'Northstar Platform Docs',
  tagline: 'The Docusaurus rendering of the shared Northstar content',
  url: 'https://zhouyaoji.github.io',
  baseUrl: '/northstar-docs-frameworks/docusaurus/',
  organizationName: 'zhouyaoji',
  projectName: 'northstar-docs-frameworks',
  trailingSlash: true,
  onBrokenLinks: 'throw',
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'throw',
    },
  },
  presets: [
    [
      'classic',
      {
        docs: {
          path: '../../content/markdown',
          routeBasePath: '/',
          sidebarPath: require.resolve('./sidebars.js'),
        },
        blog: false,
        theme: {},
      },
    ],
  ],
  themeConfig: {
    navbar: {
      title: 'Northstar · Docusaurus',
      items: [
        { href: 'https://zhouyaoji.github.io/northstar-docs-frameworks/', label: 'All renderers', position: 'right' },
        { href: 'https://github.com/zhouyaoji/northstar-docs-frameworks', label: 'GitHub', position: 'right' },
      ],
    },
    footer: {
      style: 'dark',
      copyright: 'Fictional Northstar Platform documentation.',
    },
  },
};

module.exports = config;
