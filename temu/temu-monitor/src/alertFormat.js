/** 飞书告警行格式（对齐插件 itemLines / editLink） */

export function editLink(productId, base = 'https://agentseller.temu.com') {
  const b = String(base || 'https://agentseller.temu.com').replace(/\/$/, '');
  return `${b}/goods/edit?from=productList&productId=${productId}`;
}

/**
 * @param {Array<{productId?:string,name?:string,skc?:string,parentId?:string}>} items
 * @param {number|null} total
 */
export function itemLines(items, total, editBaseUrl) {
  const lines = [];
  if (Array.isArray(items) && items.length) {
    for (const it of items) {
      const nm = String(it.name || '商品').replace(/[[\]]/g, '').slice(0, 30);
      const pid = it.productId || it.parentId || '';
      const skc = it.skc || it.skcId || '-';
      if (pid) lines.push(`• [${nm}](${editLink(pid, editBaseUrl)})  SKC ${skc}`);
      else lines.push(`• ${nm}  SKC ${skc}`);
    }
    if (typeof total === 'number' && total > items.length) {
      lines.push(`_（本页可见 ${items.length} 条，共 ${total} 条，其余在其它页）_`);
    }
  } else if (typeof total === 'number' && total > 0) {
    lines.push(`_（当前页未显示具体商品，共 ${total} 条）_`);
  }
  return lines;
}
