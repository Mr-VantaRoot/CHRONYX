/** Match an event against the optional category, status, and priority filters. */
export function matchesEventFilters(event, {category = 'All', status = 'All', priority = 'All'} = {}) {
  return (
    (category === 'All' || event.category === category) &&
    (status === 'All' || event.status === status) &&
    (priority === 'All' || event.priority === priority)
  );
}
