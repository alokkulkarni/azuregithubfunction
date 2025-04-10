import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pymongo import MongoClient
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import logging
from typing import Optional, Dict
from plotly.subplots import make_subplots

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# MongoDB connection
@st.cache_resource
def get_mongodb_connection():
    try:
        mongo_uri = os.getenv('MONGO_URI')
        if not mongo_uri:
            raise ValueError("MONGO_URI environment variable not set")
        
        client = MongoClient(mongo_uri)
        db = client.get_database()
        return {
            'github': db['github'],
            'sonar': db['sonar'],
            'nexus': db['nexus']
        }
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {str(e)}")
        return None

def get_repositories():
    """Get list of all repositories from GitHub collection."""
    try:
        collections = get_mongodb_connection()
        if not collections:
            return []
        
        return list(collections['github'].distinct('repository'))
    except Exception as e:
        logger.error(f"Error getting repositories: {str(e)}")
        return []

def get_repository_data(repo_name: str) -> Optional[Dict]:
    """Get latest data for a repository from all collections."""
    try:
        collections = get_mongodb_connection()
        if not collections:
            return None
        
        # Get latest data from each collection
        github_data = collections['github'].find_one(
            {'repository': repo_name},
            sort=[('timestamp', -1)]
        )
        
        sonar_data = collections['sonar'].find_one(
            {'repository': repo_name},
            sort=[('timestamp', -1)]
        )
        
        nexus_data = collections['nexus'].find_one(
            {'repository': repo_name},
            sort=[('timestamp', -1)]
        )
        
        # Extract the data field from each document
        return {
            'github': github_data.get('data') if github_data else None,
            'sonar': sonar_data.get('data') if sonar_data else None,
            'nexus': nexus_data.get('data') if nexus_data else None
        }
    except Exception as e:
        logger.error(f"Error getting repository data: {str(e)}")
        return None

def create_pr_metrics_chart(data: Dict) -> Optional[go.Figure]:
    """Create a chart for PR metrics."""
    try:
        if not data or 'pr_metrics' not in data:
            return None

        pr_metrics = data['pr_metrics']
        
        # Create subplots with compatible chart types
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'PR State Distribution',
                'PR Cycle Times (hours)',
                'PR Size Distribution',
                'Review Times (hours)'
            ),
            specs=[
                [{"type": "domain"}, {"type": "xy"}],
                [{"type": "xy"}, {"type": "xy"}]
            ]
        )

        # PR State Distribution (Pie Chart)
        states = ['Open', 'Closed', 'Merged']
        values = [
            pr_metrics.get('open_prs', 0),
            pr_metrics.get('closed_prs', 0),
            pr_metrics.get('merged_prs', 0)
        ]
        fig.add_trace(
            go.Pie(
                labels=states,
                values=values,
                name='PR States',
                hole=0.4
            ),
            row=1, col=1
        )

        # PR Cycle Times (Bar Chart)
        cycle_times = pr_metrics.get('avg_cycle_times', {})
        states = ['Total', 'Closed', 'Open', 'Merged']
        avg_times = [
            cycle_times.get('total', 0),
            cycle_times.get('closed', 0),
            cycle_times.get('open', 0),
            cycle_times.get('merged', 0)
        ]
        median_times = [
            pr_metrics.get('median_cycle_times', {}).get('total', 0),
            pr_metrics.get('median_cycle_times', {}).get('closed', 0),
            pr_metrics.get('median_cycle_times', {}).get('open', 0),
            pr_metrics.get('median_cycle_times', {}).get('merged', 0)
        ]

        fig.add_trace(
            go.Bar(
                name='Average Cycle Time',
                x=states,
                y=avg_times,
                text=[f'{t:.1f}h' for t in avg_times],
                textposition='auto'
            ),
            row=1, col=2
        )

        fig.add_trace(
            go.Bar(
                name='Median Cycle Time',
                x=states,
                y=median_times,
                text=[f'{t:.1f}h' for t in median_times],
                textposition='auto'
            ),
            row=1, col=2
        )

        # PR Size Distribution (Bar Chart)
        size_dist = pr_metrics.get('pr_size_distribution', {})
        sizes = ['Small', 'Medium', 'Large', 'XLarge']
        values = [
            size_dist.get('small', 0),
            size_dist.get('medium', 0),
            size_dist.get('large', 0),
            size_dist.get('xlarge', 0)
        ]
        fig.add_trace(
            go.Bar(
                x=sizes,
                y=values,
                text=values,
                textposition='auto'
            ),
            row=2, col=1
        )

        # Review Times (Bar Chart)
        review_time = pr_metrics.get('review_time', {})
        times = [
            review_time.get('avg_time_to_first_review', 0),
            review_time.get('avg_review_time', 0)
        ]
        labels = ['Time to First Review', 'Average Review Time']
        fig.add_trace(
            go.Bar(
                x=labels,
                y=times,
                text=[f'{t:.1f}h' for t in times],
                textposition='auto'
            ),
            row=2, col=2
        )

        # Update layout
        fig.update_layout(
            height=800,
            showlegend=True,
            title_text='Pull Request Metrics',
            barmode='group',
            margin=dict(t=100, b=50, l=50, r=50)
        )

        # Update y-axis titles
        fig.update_yaxes(title_text="Hours", row=1, col=2)
        fig.update_yaxes(title_text="Count", row=2, col=1)
        fig.update_yaxes(title_text="Hours", row=2, col=2)

        return fig
    except Exception as e:
        logging.error(f"Error creating PR metrics chart: {str(e)}")
        return None

def create_commit_activity_chart(data):
    """Create commit activity chart."""
    if not data:
        return None
    
    commit_stats = data.get('commit_stats', {})
    if not commit_stats:
        return None
    
    # Create a DataFrame from the dates dictionary
    dates_df = pd.DataFrame({
        'Date': list(commit_stats.get('dates', {}).keys()),
        'Commits': list(commit_stats.get('dates', {}).values())
    })
    
    if dates_df.empty:
        return None
    
    # Convert Date column to datetime
    dates_df['Date'] = pd.to_datetime(dates_df['Date'])
    
    # Sort by date
    dates_df = dates_df.sort_values('Date')
    
    fig = px.line(
        dates_df,
        x='Date',
        y='Commits',
        title='Commit Activity Over Time'
    )
    
    return fig

def create_code_quality_chart(data):
    """Create code quality metrics chart."""
    if not data:
        return None
    
    metrics_df = pd.DataFrame({
        'Metric': ['Code Smells', 'Bugs', 'Vulnerabilities', 'Coverage'],
        'Count': [
            data.get('code_smells', 0),
            data.get('bugs', 0),
            data.get('vulnerabilities', 0),
            data.get('coverage', 0)
        ]
    })
    
    fig = px.bar(metrics_df, x='Metric', y='Count', title='Code Quality Metrics')
    return fig

def create_security_chart(data):
    """Create security metrics chart."""
    if not data:
        return None
    
    security_df = pd.DataFrame({
        'Severity': ['Critical', 'High', 'Medium', 'Low'],
        'Count': [
            data.get('critical_vulnerabilities', 0),
            data.get('high_vulnerabilities', 0),
            data.get('medium_vulnerabilities', 0),
            data.get('low_vulnerabilities', 0)
        ]
    })
    
    fig = px.bar(security_df, x='Severity', y='Count', title='Security Vulnerabilities')
    return fig

def create_repo_overview(data):
    """Create repository overview section."""
    if not data:
        return None
    
    repo_stats = data.get('repo_stats', {})
    
    # Create a more compact layout with 2 rows of metrics
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric("Stars", repo_stats.get('stars', 0))
    with col2:
        st.metric("Forks", repo_stats.get('forks', 0))
    with col3:
        st.metric("Watchers", repo_stats.get('watchers', 0))
    with col4:
        st.metric("Open Issues", repo_stats.get('open_issues', 0))
    with col5:
        st.metric("Size", f"{repo_stats.get('size', 0)} KB")
    with col6:
        st.metric("Language", repo_stats.get('language', 'N/A'))
    
    # Second row of metrics
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        created_at = repo_stats.get('created_at')
        created_date = pd.to_datetime(created_at).strftime('%Y-%m-%d') if created_at else 'N/A'
        st.metric("Created", created_date)
    with col2:
        updated_at = repo_stats.get('updated_at')
        updated_date = pd.to_datetime(updated_at).strftime('%Y-%m-%d') if updated_at else 'N/A'
        st.metric("Last Updated", updated_date)
    
    # Repository description with compact styling
    description = repo_stats.get('description', 'No description available')
    if description:
        st.markdown(f"""
            <div style="
                background-color: #f8f9fa;
                padding: 0.5rem;
                border-radius: 0.5rem;
                margin: 0.5rem 0;
                font-size: 0.9rem;
            ">
                {description}
            </div>
        """, unsafe_allow_html=True)
    
    # Topics and features in a single row
    col1, col2 = st.columns(2)
    
    with col1:
        topics = repo_stats.get('topics', [])
        if topics:
            st.markdown("""
                <div style="
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.25rem;
                    margin: 0.5rem 0;
                ">
            """, unsafe_allow_html=True)
            
            for topic in topics:
                st.markdown(f"""
                    <span style="
                        background-color: #e9ecef;
                        padding: 0.15rem 0.5rem;
                        border-radius: 0.75rem;
                        font-size: 0.8rem;
                    ">
                        {topic}
                    </span>
                """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
    
    with col2:
        features = {
            'Wiki': repo_stats.get('has_wiki', False),
            'Pages': repo_stats.get('has_pages', False),
            'Projects': repo_stats.get('has_projects', False),
            'Downloads': repo_stats.get('has_downloads', False),
            'Issues': repo_stats.get('has_issues', False)
        }
        
        enabled_features = [k for k, v in features.items() if v]
        if enabled_features:
            st.markdown("""
                <div style="
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.25rem;
                    margin: 0.5rem 0;
                ">
            """, unsafe_allow_html=True)
            
            for feature in enabled_features:
                st.markdown(f"""
                    <span style="
                        background-color: #d1e7dd;
                        color: #0f5132;
                        padding: 0.15rem 0.5rem;
                        border-radius: 0.75rem;
                        font-size: 0.8rem;
                    ">
                        {feature}
                    </span>
                """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)

def create_contributors_chart(data):
    """Create contributors chart."""
    if not data:
        return None
    
    contributors = data.get('contributors', {})
    if not contributors or 'contributors' not in contributors:
        return None
    
    # Get top 10 contributors
    top_contributors = sorted(
        contributors['contributors'],
        key=lambda x: x['contributions'],
        reverse=True
    )[:10]
    
    df = pd.DataFrame(top_contributors)
    fig = px.bar(
        df,
        x='login',
        y='contributions',
        title='Top 10 Contributors',
        labels={'login': 'Contributor', 'contributions': 'Number of Contributions'}
    )
    return fig

def create_branches_chart(data):
    """Create branches chart."""
    if not data:
        return None
    
    branches = data.get('branches', {})
    if not branches or 'branches' not in branches:
        return None
    
    # Count protected vs unprotected branches
    protected = sum(1 for b in branches['branches'] if b['protected'])
    unprotected = len(branches['branches']) - protected
    
    df = pd.DataFrame({
        'Type': ['Protected', 'Unprotected'],
        'Count': [protected, unprotected]
    })
    
    fig = px.pie(
        df,
        values='Count',
        names='Type',
        title='Branch Protection Status'
    )
    return fig

def create_releases_chart(data):
    """Create releases chart."""
    if not data:
        return None
    
    releases = data.get('releases', {})
    if not releases or 'releases' not in releases:
        return None
    
    # Count releases by type
    prereleases = sum(1 for r in releases['releases'] if r['prerelease'])
    drafts = sum(1 for r in releases['releases'] if r['draft'])
    published = len(releases['releases']) - prereleases - drafts
    
    df = pd.DataFrame({
        'Type': ['Published', 'Pre-releases', 'Drafts'],
        'Count': [published, prereleases, drafts]
    })
    
    fig = px.bar(
        df,
        x='Type',
        y='Count',
        title='Release Types'
    )
    return fig

def create_issues_chart(data):
    """Create issues chart."""
    if not data:
        return None
    
    issue_stats = data.get('issue_stats', {})
    if not issue_stats:
        return None
    
    df = pd.DataFrame({
        'Status': ['Open', 'Closed'],
        'Count': [
            issue_stats.get('open_issues', 0),
            issue_stats.get('closed_issues', 0)
        ]
    })
    
    fig = px.pie(
        df,
        values='Count',
        names='Status',
        title='Issue Status Distribution'
    )
    return fig

def main():
    st.set_page_config(
        page_title="Repository Analysis Dashboard",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("Repository Analysis Dashboard")
    
    # Sidebar for repository selection
    st.sidebar.title("Repository Selection")
    repositories = get_repositories()
    selected_repo = st.sidebar.selectbox(
        "Select Repository",
        repositories,
        index=0 if repositories else None
    )
    
    if selected_repo:
        # Get repository data
        repo_data = get_repository_data(selected_repo)
        
        if repo_data:
            github_data = repo_data['github']
            sonar_data = repo_data['sonar']
            nexus_data = repo_data['nexus']
            
            # Create tabs for different sections
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "Overview", "PR Metrics", "Code Quality", "Security", "Raw Data"
            ])
            
            with tab1:
                if github_data:
                    create_repo_overview(github_data)
                    
                    # Create a 2x2 grid for charts
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Contributors section
                        contributors_chart = create_contributors_chart(github_data)
                        if contributors_chart:
                            st.plotly_chart(contributors_chart, use_container_width=True)
                        
                        # Branches section
                        branches_chart = create_branches_chart(github_data)
                        if branches_chart:
                            st.plotly_chart(branches_chart, use_container_width=True)
                    
                    with col2:
                        # Commit activity section
                        commit_chart = create_commit_activity_chart(github_data)
                        if commit_chart:
                            st.plotly_chart(commit_chart, use_container_width=True)
                        
                        # Releases section
                        releases_chart = create_releases_chart(github_data)
                        if releases_chart:
                            st.plotly_chart(releases_chart, use_container_width=True)
                    
                    # Issues section (full width)
                    issues_chart = create_issues_chart(github_data)
                    if issues_chart:
                        st.plotly_chart(issues_chart, use_container_width=True)
                else:
                    st.info("No GitHub data available")
            
            with tab2:
                if github_data:
                    pr_chart = create_pr_metrics_chart(github_data)
                    if pr_chart:
                        st.plotly_chart(pr_chart, use_container_width=True)
                    else:
                        st.info("No PR metrics data available")
                else:
                    st.info("No GitHub data available")
            
            with tab3:
                if sonar_data:
                    quality_chart = create_code_quality_chart(sonar_data)
                    if quality_chart:
                        st.plotly_chart(quality_chart, use_container_width=True)
                    else:
                        st.info("No code quality data available")
                else:
                    st.info("No SonarQube data available")
            
            with tab4:
                if nexus_data:
                    security_chart = create_security_chart(nexus_data)
                    if security_chart:
                        st.plotly_chart(security_chart, use_container_width=True)
                    else:
                        st.info("No security data available")
                else:
                    st.info("No NexusIQ data available")
            
            with tab5:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.subheader("GitHub Data")
                    st.json(github_data)
                
                with col2:
                    st.subheader("SonarQube Data")
                    st.json(sonar_data)
                
                with col3:
                    st.subheader("NexusIQ Data")
                    st.json(nexus_data)
        else:
            st.error("No data available for the selected repository")
    else:
        st.info("No repositories available. Please run the scanner first.")

if __name__ == "__main__":
    main() 