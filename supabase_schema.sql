-- Enable Row Level Security
ALTER DATABASE postgres SET timezone TO 'UTC';

-- Create profiles table (linked to auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
  id uuid references auth.users on delete cascade not null primary key,
  username text unique,
  full_name text,
  avatar_url text,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Enable RLS on profiles
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Create policies for profiles
CREATE POLICY "Public profiles are viewable by everyone" ON public.profiles
  FOR SELECT USING (true);

CREATE POLICY "Users can insert their own profile" ON public.profiles
  FOR INSERT WITH CHECK (auth.uid() = id);

CREATE POLICY "Users can update their own profile" ON public.profiles
  FOR UPDATE USING (auth.uid() = id);

-- Create bench favorites table
CREATE TABLE IF NOT EXISTS public.bench_favorites (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users on delete cascade not null,
  bench_id integer not null,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  unique(user_id, bench_id)
);

-- Enable RLS on bench_favorites
ALTER TABLE public.bench_favorites ENABLE ROW LEVEL SECURITY;

-- Create policies for bench_favorites
CREATE POLICY "Users can view their own favorites" ON public.bench_favorites
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own favorites" ON public.bench_favorites
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own favorites" ON public.bench_favorites
  FOR DELETE USING (auth.uid() = user_id);

-- Create bench comments table
CREATE TABLE IF NOT EXISTS public.bench_comments (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users on delete cascade not null,
  bench_id integer not null,
  content text not null,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Enable RLS on bench_comments
ALTER TABLE public.bench_comments ENABLE ROW LEVEL SECURITY;

-- Create policies for bench_comments
CREATE POLICY "Comments are viewable by everyone" ON public.bench_comments
  FOR SELECT USING (true);

CREATE POLICY "Users can insert their own comments" ON public.bench_comments
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own comments" ON public.bench_comments
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own comments" ON public.bench_comments
  FOR DELETE USING (auth.uid() = user_id);

-- Create bench status table (want to go / been there)
CREATE TABLE IF NOT EXISTS public.bench_status (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users on delete cascade not null,
  bench_id integer not null,
  status text not null check (status in ('want_to_go', 'been_there')),
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null,
  unique(user_id, bench_id)
);

-- Enable RLS on bench_status
ALTER TABLE public.bench_status ENABLE ROW LEVEL SECURITY;

-- Create policies for bench_status
CREATE POLICY "Users can view their own status" ON public.bench_status
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own status" ON public.bench_status
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own status" ON public.bench_status
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own status" ON public.bench_status
  FOR DELETE USING (auth.uid() = user_id);

-- Create missing bench reports table
CREATE TABLE IF NOT EXISTS public.missing_bench_reports (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users on delete cascade not null,
  lat double precision not null,
  lng double precision not null,
  description text,
  image_url text,
  status text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Enable RLS on missing_bench_reports
ALTER TABLE public.missing_bench_reports ENABLE ROW LEVEL SECURITY;

-- Create policies for missing_bench_reports
CREATE POLICY "Users can view their own reports" ON public.missing_bench_reports
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own reports" ON public.missing_bench_reports
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own reports" ON public.missing_bench_reports
  FOR UPDATE USING (auth.uid() = user_id);

-- Create bench issue reports table
CREATE TABLE IF NOT EXISTS public.bench_issue_reports (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users on delete cascade not null,
  bench_id integer not null,
  issue_type text not null check (issue_type in ('damaged', 'missing', 'inappropriate', 'other')),
  description text not null,
  image_url text,
  status text not null default 'pending' check (status in ('pending', 'resolved', 'rejected')),
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Enable RLS on bench_issue_reports
ALTER TABLE public.bench_issue_reports ENABLE ROW LEVEL SECURITY;

-- Create policies for bench_issue_reports
CREATE POLICY "Users can view their own issue reports" ON public.bench_issue_reports
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own issue reports" ON public.bench_issue_reports
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own issue reports" ON public.bench_issue_reports
  FOR UPDATE USING (auth.uid() = user_id);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_bench_favorites_user_id ON public.bench_favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_bench_favorites_bench_id ON public.bench_favorites(bench_id);
CREATE INDEX IF NOT EXISTS idx_bench_comments_bench_id ON public.bench_comments(bench_id);
CREATE INDEX IF NOT EXISTS idx_bench_comments_user_id ON public.bench_comments(user_id);
CREATE INDEX IF NOT EXISTS idx_bench_status_user_id ON public.bench_status(user_id);
CREATE INDEX IF NOT EXISTS idx_bench_status_bench_id ON public.bench_status(bench_id);
CREATE INDEX IF NOT EXISTS idx_missing_reports_user_id ON public.missing_bench_reports(user_id);
CREATE INDEX IF NOT EXISTS idx_missing_reports_location ON public.missing_bench_reports(lat, lng);
CREATE INDEX IF NOT EXISTS idx_issue_reports_user_id ON public.bench_issue_reports(user_id);
CREATE INDEX IF NOT EXISTS idx_issue_reports_bench_id ON public.bench_issue_reports(bench_id);

-- Function to automatically create profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user() 
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.profiles (id, username, full_name, avatar_url)
  VALUES (new.id, new.raw_user_meta_data->>'username', new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'avatar_url');
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to automatically create profile on user signup
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Function to handle updated_at timestamp
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = timezone('utc'::text, now());
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add updated_at triggers
CREATE TRIGGER handle_updated_at_profiles
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER handle_updated_at_comments
  BEFORE UPDATE ON public.bench_comments
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER handle_updated_at_status
  BEFORE UPDATE ON public.bench_status
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER handle_updated_at_missing_reports
  BEFORE UPDATE ON public.missing_bench_reports
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER handle_updated_at_issue_reports
  BEFORE UPDATE ON public.bench_issue_reports
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();