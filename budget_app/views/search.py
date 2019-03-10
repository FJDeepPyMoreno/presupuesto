from django.core.paginator import EmptyPage
from django.conf import settings
from budget_app.models import *
from helpers import *
from paginator import DiggPaginator as Paginator

PAGE_LENGTH = 10


def search(request):
    c = get_context(request, css_class='body-search', title='')

    c['query'] = request.GET.get('q', '')
    populate_latest_budget(c)
    c['selected_year'] = str(request.GET.get('year', c['latest_budget'].year))
    c['page'] = request.GET.get('page', 1)
    c['query_string'] = "year=%s&q=%s&" % (c['selected_year'], c['query'])

    # If no parameter is given we show results for the latest budget. In order
    # to search across all budgets one needs to request that explicitly.
    if c['selected_year'] != "all":
        year = c['selected_year']
        budgets = Budget.objects.filter(entity__id=get_main_entity(c).id, year=year)
        budget = budgets[0] if len(budgets)>0 else None
    else:
        year = None
        budget = None

    # Get search results
    c['years'] = map(str, Budget.objects.get_years(get_main_entity(c).id))

    c['terms'] = list(GlossaryTerm.objects.search(c['query'], c['LANGUAGE_CODE']))

    if hasattr(settings, 'SEARCH_ENTITIES') and settings.SEARCH_ENTITIES:
        c['entities'] = list(Entity.objects.search(c['query']))
        c['show_entity_names'] = True

    if hasattr(settings, 'SHOW_SECTION_PAGES') and settings.SHOW_SECTION_PAGES:
        c['departments'] = list(InstitutionalCategory.objects.search_departments(c['query'], budget))

    all_items = list(BudgetItem.objects.search(c['query'], year, c['LANGUAGE_CODE'], c['page']))
    try:
        c['items'] = Paginator(all_items, PAGE_LENGTH, body=6, padding=2).page(c['page'])
    except EmptyPage:
        pass

    if hasattr(settings, 'SHOW_PAYMENTS') and settings.SHOW_PAYMENTS:
        all_payments = list(Payment.objects.search(c['query'], year, c['LANGUAGE_CODE']))
        try:
            c['payments'] = Paginator(all_payments, PAGE_LENGTH, body=6, padding=2).page(c['page'])
        except EmptyPage:
            pass

    # Consolidate articles and headings search results, to avoid duplicates.
    articles = list(EconomicCategory.objects.search_articles(c['query'], budget))
    headings = list(EconomicCategory.objects.search_headings(c['query'], budget))
    c['income_articles_ids'] = list(set( article.uid() for article in articles if not article.expense ))
    c['expense_articles_ids'] = list(set( article.uid() for article in articles if article.expense ))
    c['headings_per_income_article'] = {}
    c['headings_per_expense_article'] = {}
    for heading in headings:
        s = c['headings_per_expense_article'] if heading.expense else c['headings_per_income_article']
        if not s.get(heading.article, None):
            s[heading.article] = set()
        s[heading.article].add(heading.heading)

    # Consolidate policies and programmes search results, to avoid duplicates
    # XXX: We're searching only in top-level entity, the other ones are spotty,
    # not sure it's worth the effort; plus the search results UX is complicated.
    policies = list(FunctionalCategory.objects.search_policies(c['query'], budget))
    programmes = list(FunctionalCategory.objects.search_programmes(c['query'], budget))
    c['policies_ids'] = list(set(policy.uid() for policy in policies))
    c['programmes_per_policy'] = {}
    for programme in programmes:
        if not c['programmes_per_policy'].get(programme.policy, None):
            c['programmes_per_policy'][programme.policy] = set()
        c['programmes_per_policy'][programme.policy].add(programme.programme)

    # XXX: Note we only have top-level descriptions. Beware on the view not to use
    # the wrong descriptions. We should fetch the descriptions from the DB together with
    # the results if needed.
    populate_descriptions(c)

    # Count the results
    c['results_size'] = len(c['terms']) + \
                        (len(c['entities']) if 'entities' in c else 0) + \
                        (len(c['departments']) if 'departments' in c else 0) + \
                        len(c['policies_ids']) + \
                        len(c['income_articles_ids']) + \
                        len(c['expense_articles_ids']) + \
                        len(all_items) + \
                        (len(all_payments) if 'payments' in c else 0)
    for headings in c['headings_per_income_article'].values():
        c['results_size'] += len(headings)
    for headings in c['headings_per_expense_article'].values():
        c['results_size'] += len(headings)
    for programmes in c['programmes_per_policy'].values():
        c['results_size'] += len(programmes)

    # Extra info
    c['formatter'] = add_thousands_separator
    c['main_entity_level'] = settings.MAIN_ENTITY_LEVEL

    return render_response('search/index.html', c)
