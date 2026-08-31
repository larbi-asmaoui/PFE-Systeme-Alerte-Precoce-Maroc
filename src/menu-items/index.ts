// import { IconDashboard, IconKey, IconTypography, IconPalette, IconShadow, IconWindmill, IconBrandChrome, IconHelp } from '@tabler/icons-react';

// // ==============================|| MENU ITEMS ||============================== //

// export interface MenuItem {
//   id: string;
//   title?: string;
//   caption?: string;
//   type?: 'group' | 'item' | 'collapse';
//   url?: string;
//   icon?: any;
//   external?: boolean;
//   target?: boolean;
//   breadcrumbs?: boolean;
//   disabled?: boolean;
//   chip?: {
//     label: string;
//     color?: 'primary' | 'secondary' | 'default' | 'error' | 'info' | 'success' | 'warning';
//     variant?: 'filled' | 'outlined';
//     size?: 'small' | 'medium';
//     avatar?: React.ReactElement;
//   };
//   children?: MenuItem[];
// }

// const dashboard: MenuItem = {
//   id: 'dashboard',
//   title: 'Dashboard',
//   type: 'group',
//   children: [
//     {
//       id: 'default',
//       title: 'Dashboard',
//       type: 'item',
//       url: '/',
//       icon: IconDashboard, // Next.js routing uses / for default dashboard
//       breadcrumbs: false
//     }
//   ]
// };

// const pages: MenuItem = {
//   id: 'pages',
//   title: 'Pages',
//   caption: 'Pages Caption',
//   type: 'group',
//   children: [
//     {
//       id: 'authentication',
//       title: 'Authentication',
//       type: 'collapse',
//       icon: IconKey,
//       children: [
//         {
//           id: 'login',
//           title: 'Login',
//           type: 'item',
//           url: '/login', // Adjusted for Next.js app/login structure
//           target: false // No need for new tab usually
//         },
//         {
//             id: 'register',
//             title: 'Register',
//             type: 'item',
//             url: '/register',
//             target: false
//         }
//       ]
//     }
//   ]
// };

// const utilities: MenuItem = {
//   id: 'utilities',
//   title: 'Utilities',
//   type: 'group',
//   children: [
//     {
//       id: 'util-typography',
//       title: 'Typography',
//       type: 'item',
//       url: '/typography',
//       icon: IconTypography,
//       breadcrumbs: false
//     },
//     {
//       id: 'util-color',
//       title: 'Color',
//       type: 'item',
//       url: '/color',
//       icon: IconPalette,
//       breadcrumbs: false
//     },
//     {
//       id: 'util-shadow',
//       title: 'Shadow',
//       type: 'item',
//       url: '/shadow',
//       icon: IconShadow,
//       breadcrumbs: false
//     }
//   ]
// };

// const other: MenuItem = {
//   id: 'sample-docs-roadmap',
//   type: 'group',
//   children: [
//     {
//       id: 'sample-page',
//       title: 'Sample Page',
//       type: 'item',
//       url: '/sample-page',
//       icon: IconBrandChrome,
//       breadcrumbs: false
//     },
//     {
//       id: 'documentation',
//       title: 'Documentation',
//       type: 'item',
//       url: 'https://codedthemes.gitbook.io/berry/',
//       icon: IconHelp,
//       external: true,
//       target: true
//     }
//   ]
// };

// const menuItems: { items: MenuItem[] } = {
//   items: [dashboard, pages, utilities, other]
// };

// export default menuItems;
// //

import {
  IconDashboard,
  IconMapPin,
  IconUsers,
  IconSettings,
} from "@tabler/icons-react";

export interface MenuItem {
  id: string;
  title?: string;
  caption?: string;
  type?: "group" | "item" | "collapse";
  url?: string;
  icon?: any;
  external?: boolean;
  target?: boolean;
  breadcrumbs?: boolean;
  disabled?: boolean;
  chip?: any;
  children?: MenuItem[];
}

const dashboard: MenuItem = {
  id: "dashboard",
  title: "Surveillance",
  type: "group",
  children: [
    {
      id: "default",
      title: "Tableau de Bord",
      type: "item",
      url: "/",
      icon: IconDashboard,
      breadcrumbs: false,
    },
    {
      id: "stations",
      title: "Historique Stations",
      type: "item",
      url: "/stations",
      icon: IconMapPin,
      breadcrumbs: false,
    },
  ],
};

const administration: MenuItem = {
  id: "administration",
  title: "Administration",
  type: "group",
  children: [
    {
      id: "users",
      title: "Utilisateurs",
      type: "item",
      url: "/users",
      icon: IconUsers,
      breadcrumbs: false,
    },
    {
      id: "settings",
      title: "Configuration",
      type: "item",
      url: "/settings",
      icon: IconSettings,
      breadcrumbs: false,
    },
  ],
};

export default { items: [dashboard, administration] };
