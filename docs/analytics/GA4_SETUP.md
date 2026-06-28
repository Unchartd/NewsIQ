# GA4 Console Setup Guide

To ensure that the custom parameters sent by the NewsIQ analytics library are searchable and indexable in GA4 Reports and Explorations, you must manually register them as **Custom Definitions** inside the Google Analytics Admin Console.

---

## Step 1: Access Custom Definitions in GA4

1. Open [Google Analytics](https://analytics.google.com/) and navigate to your NewsIQ Property.
2. Click the gear icon (**Admin**) in the bottom-left corner.
3. In the *Data Display* column, click on **Custom definitions**.

---

## Step 2: Register Custom Dimensions (Event Scope)

For each dimension below, click **Create custom dimensions** in the top-right and fill in the details:

1. **Story ID**
   - **Dimension name**: `Story ID`
   - **Scope**: `Event`
   - **Description**: Database UUID of the news story cluster
   - **Event parameter**: `story_id`

2. **Story Headline**
   - **Dimension name**: `Story Headline`
   - **Scope**: `Event`
   - **Description**: Headline of the clustered news item
   - **Event parameter**: `headline`

3. **Story Category**
   - **Dimension name**: `Story Category`
   - **Scope**: `Event`
   - **Description**: Primary category class
   - **Event parameter**: `story_category`

4. **Summary Type**
   - **Dimension name**: `Summary Type`
   - **Scope**: `Event`
   - **Description**: Active summary depth: one_line, short, or detailed
   - **Event parameter**: `summary_type`

---

## Step 3: Register Custom Dimensions (User Scope)

Click the **User properties** tab in the Custom definitions panel, click **Create custom dimensions**, and register user scopes:

1. **User Tier**
   - **Dimension name**: `User Tier`
   - **Scope**: `User`
   - **Description**: Role of the user: guest, user, premium, admin
   - **User property**: `user_tier`

2. **Subscription Status**
   - **Dimension name**: `Subscription Status`
   - **Scope**: `User`
   - **Description**: Pricing level: free, pro, enterprise
   - **User property**: `subscription_status`

---

## Step 4: Register Custom Metrics

Click the **Custom metrics** tab in the Custom definitions panel, click **Create custom metrics**, and register numerical metrics:

1. **Active Reading Duration**
   - **Metric name**: `Active Reading Duration`
   - **Scope**: `Event`
   - **Description**: Seconds user spent actively reading the page
   - **Event parameter**: `duration_seconds`
   - **Unit of measurement**: `Seconds`

2. **Conflict Count**
   - **Metric name**: `Conflict Count`
   - **Scope**: `Event`
   - **Description**: Clustered contradictions surfaced in the story differences table
   - **Event parameter**: `conflict_count`
   - **Unit of measurement**: `Standard`
