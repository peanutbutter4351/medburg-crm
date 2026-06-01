import sys
content = open('templates/doctors/admin_dashboard.html', 'r', encoding='utf-8').read()

nav = '''
<!-- ─── Dashboard Navigation ─── -->
<div class="d-flex justify-content-center mb-5 mt-2">
    <div class="btn-group shadow-sm" role="group" style="border-radius: var(--radius-md); overflow: hidden;">
        <button type="button" class="btn btn-outline-primary fw-bold px-4 py-2" onclick="switchDashboardSection('prepaid')" id="btn-prepaid">PREPAID</button>
        <button type="button" class="btn btn-primary fw-bold px-4 py-2" onclick="switchDashboardSection('home')" id="btn-home">HOME</button>
        <button type="button" class="btn btn-outline-primary fw-bold px-4 py-2" onclick="switchDashboardSection('postpaid')" id="btn-postpaid">POSTPAID</button>
    </div>
</div>

<div id="dashboard-prepaid-section" style="display: none;">
'''

content = content.replace('<!-- ─── Prepaid Section ───────────────────────── -->', nav + '<!-- ─── Prepaid Section ───────────────────────── -->', 1)
content = content.replace('<!-- ─── Postpaid Section ──────────────────────── -->', '</div>\n\n<div id="dashboard-postpaid-section" style="display: none;">\n<!-- ─── Postpaid Section ──────────────────────── -->', 1)

activity_feed_start = content.find('<!-- ─── Unified Company Activity Feed ────────────────── -->')
activity_feed_end = content.find('<!-- ─── Analytics & KPI Visualizations ─── -->')
analytics_start = activity_feed_end
analytics_end = content.find('{{ admin_analytics|json_script:"admin-analytics-data" }}')

activity_feed = content[activity_feed_start:activity_feed_end]
analytics = content[analytics_start:analytics_end]

before = content[:activity_feed_start]
after = content[analytics_end:]

new_content = before + '</div>\n\n<div id="dashboard-home-section">\n' + analytics + '\n' + activity_feed + '\n</div>\n\n' + after

js = '''
    function switchDashboardSection(section) {
        const sections = ['prepaid', 'home', 'postpaid'];
        sections.forEach(s => {
            document.getElementById('dashboard-' + s + '-section').style.display = (s === section) ? 'block' : 'none';
            const btn = document.getElementById('btn-' + s);
            if (s === section) {
                btn.classList.remove('btn-outline-primary');
                btn.classList.add('btn-primary');
            } else {
                btn.classList.remove('btn-primary');
                btn.classList.add('btn-outline-primary');
            }
        });
    }

    // ── Chart.js Initialization ──
'''
new_content = new_content.replace('    // ── Chart.js Initialization ──', js)

open('templates/doctors/admin_dashboard.html', 'w', encoding='utf-8').write(new_content)
print('Done.')
