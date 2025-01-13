import re
import spacy
from datetime import datetime
import os
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from collections import defaultdict
import logging

# ----------------------------- Configuration -----------------------------

# List of paths to the generated scraped files
SCRAPED_FILE_PATHS = [
    'la_prensa_10-11-2024_10-12-2024.txt',  # Replace with your actual file paths
    'la_estrella_10-11-2024_10-12-2024.txt'
]

# Number of top trending topics to extract based on frequency
TOP_N_TOPICS = 5  # Changed to 5 as per your requirement

# Number of Sample Headlines per Topic
SAMPLE_HEADLINES_PER_TOPIC = 5

# Output Directory
OUTPUT_DIR = '.'  # Current directory; change as needed

# Custom Stopwords (optional)
CUSTOM_STOPWORDS = {'dano', 'description'}  # Added 'description' to remove it from analysis

# ----------------------------- Helper Functions -----------------------------

def load_entries(file_path):
    """
    Reads a scraped file and extracts headlines and descriptions.
    Supports two formats:
    1. Format with Headline and Description:
        Category: [Category]
        Headline: [Headline]
        Description: [Description]
        Date: [Date]
    2. Format with Headline and Summary:
        Category: [Category]
        [Headline]
        Date: [Date]
        Summary: [Summary]
    --------------------------------------------------------------------------------
    """
    entries = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            # Split the content by the separator line
            raw_entries = content.split('-' * 80)
            for raw_entry in raw_entries:
                lines = raw_entry.strip().split('\n')
                if not lines or len(lines) < 3:
                    continue  # Skip incomplete entries

                # Initialize default values
                headline = ""
                description = ""

                # Check the format based on the presence of 'Headline:' or 'Summary:'
                if lines[1].startswith('Headline:'):
                    # Format 1
                    try:
                        headline = lines[1].split(':', 1)[1].strip()
                        description = lines[2].split(':', 1)[1].strip()
                    except IndexError:
                        print(f"Unexpected format in file '{file_path}' for entry: {raw_entry[:30]}...")
                else:
                    # Format 2
                    try:
                        headline = lines[1].strip()
                        # Assuming 'Summary:' is always present in this format
                        if lines[3].startswith('Summary:'):
                            description = lines[3].split(':', 1)[1].strip().strip('"')
                        else:
                            description = lines[3].strip()
                    except IndexError:
                        print(f"Unexpected format in file '{file_path}' for entry: {raw_entry[:30]}...")

                if headline or description:
                    entries.append({'headline': headline, 'description': description})
        print(f"Extracted {len(entries)} entries from '{file_path}'.")
    except FileNotFoundError:
        print(f"File '{file_path}' not found. Please check the path and try again.")
    except Exception as e:
        print(f"An error occurred while reading the file '{file_path}': {e}")
    return entries


def add_custom_stopwords(nlp, custom_stopwords):
    """
    Adds custom stopwords to the SpaCy NLP model.
    """
    for stopword in custom_stopwords:
        nlp.vocab[stopword].is_stop = True
    if custom_stopwords:
        print(f"Added {len(custom_stopwords)} custom stopwords.")


def preprocess_entries(entries, nlp):
    """
    Preprocesses entries to extract and clean text from headlines and descriptions.
    Excludes text that contains numeric characters or any stopwords.
    Returns both processed texts and their corresponding headlines.
    """
    processed_texts = []
    corresponding_headlines = []
    for entry in entries:
        combined_text = f"{entry['headline']} {entry['description']}"
        doc = nlp(combined_text)
        tokens = []
        for token in doc:
            # Remove punctuation, numbers, and stopwords
            if token.is_stop or token.is_punct or token.like_num:
                continue
            if token.is_alpha and len(token.text) > 2:
                tokens.append(token.lemma_.lower())
        if tokens:
            processed_texts.append(" ".join(tokens))
            corresponding_headlines.append(entry['headline'])
    print(f"Processed {len(processed_texts)} entries for text analysis.")
    return processed_texts, corresponding_headlines


def export_trending_topics(topics, summaries, sample_headlines, topics_words, output_dir='.',
                           filename_prefix='trending_topics'):
    """
    Exports the trending topics to a text file with today's date.
    """
    today_str = datetime.now().strftime('%d-%m-%Y')
    filename = f"{filename_prefix}_{today_str}.txt"
    filepath = os.path.join(output_dir, filename)

    try:
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(f"Trending Topics as of {today_str}\n")
            file.write("=" * 80 + "\n\n")
            for idx, topic in enumerate(topics, 1):
                topic_num = topic.Topic
                topic_words = topics_words.get(topic_num, [])
                summary = summaries.get(topic_num, "No summary available.")
                headlines = sample_headlines.get(topic_num, [])
                file.write(f"Topic {idx}: {summary}\n")
                file.write(f"   Top Words: {', '.join(topic_words)}\n")
                file.write("   Sample Headlines:\n")
                for headline in headlines:
                    file.write(f"      - {headline}\n")
                file.write("\n")
        print(f"Trending topics exported to '{filepath}'.")
    except Exception as e:
        print(f"An error occurred while writing to the file '{filepath}': {e}")


def export_topic_modeling_results(topics, summaries, sample_headlines, topics_words, output_dir='.',
                                  filename_prefix='topic_modeling'):
    """
    Exports the topic modeling results along with summaries and sample headlines to a text file with today's date.
    """
    today_str = datetime.now().strftime('%d-%m-%Y')
    filename = f"{filename_prefix}_{today_str}.txt"
    filepath = os.path.join(output_dir, filename)

    try:
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(f"Topic Modeling Results as of {today_str}\n")
            file.write("=" * 80 + "\n\n")
            for idx, topic in enumerate(topics, 1):
                topic_num = topic.Topic
                topic_words = topics_words.get(topic_num, [])
                summary = summaries.get(topic_num, "No summary available.")
                headlines = sample_headlines.get(topic_num, [])
                file.write(f"Topic {idx}:\n")
                file.write(f"   Summary: {summary}\n")
                file.write(f"   Top Words: {', '.join(topic_words)}\n")
                file.write(f"   Sample Headlines:\n")
                for headline in headlines:
                    file.write(f"      - {headline}\n")
                file.write("\n")
        print(f"Topic modeling results exported to '{filepath}'.")
    except Exception as e:
        print(f"An error occurred while writing to the file '{filepath}': {e}")


def main():
    # Initialize logging for better debugging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Initialize SpaCy with Spanish language model
    try:
        nlp = spacy.load('es_core_news_sm')
        print("SpaCy Spanish model loaded successfully.")
    except OSError:
        print("SpaCy Spanish model not found. Please run:")
        print("python -m spacy download es_core_news_sm")
        return

    # Add custom stopwords if any
    add_custom_stopwords(nlp, CUSTOM_STOPWORDS)

    # Step 1: Load entries (headlines and descriptions) from the scraped files
    entries = []
    for file_path in SCRAPED_FILE_PATHS:
        file_entries = load_entries(file_path)
        entries.extend(file_entries)
    if not entries:
        print("No entries to process. Exiting.")
        return

    # Step 2: Preprocess entries to extract clean text and collect corresponding headlines
    processed_texts, processed_headlines = preprocess_entries(entries, nlp)
    if not processed_texts:
        print("No text to analyze after preprocessing. Exiting.")
        return

    # Optional: Inspect some preprocessed texts
    print("\nSample of Preprocessed Texts:")
    for i in range(min(5, len(processed_texts))):
        print(f"{i+1}. {processed_texts[i]}")
    print("\n")

    # Step 3: Perform Topic Modeling with BERTopic
    try:
        # Use a multilingual embedding model that supports Spanish
        embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        topic_model = BERTopic(
            language="spanish",
            embedding_model=embedding_model,
            nr_topics=TOP_N_TOPICS,  # Correct parameter name
            min_topic_size=10        # Adjust based on your dataset size
        )
        topics, probabilities = topic_model.fit_transform(processed_texts)
        print("BERTopic modeling completed.")
    except Exception as e:
        print(f"An error occurred during BERTopic modeling: {e}")
        return

    # Optional: Visualize Topics (Requires Plotly)
    try:
        import plotly.io as pio
        pio.renderers.default = "browser"  # Change to "notebook" if running in a notebook environment
        topic_model.visualize_topics().write_html("topics_visualization.html")
        print("Topics visualization saved as 'topics_visualization.html'.")
    except ImportError:
        print("Plotly not installed. Skipping visualization.")
    except Exception as e:
        print(f"An error occurred during visualization: {e}")

    # Step 4: Get topic information
    topic_info = topic_model.get_topic_info()
    # Remove the -1 topic which is outliers
    topic_info = topic_info[topic_info.Topic != -1]
    # Get the top N topics
    top_topics = topic_info.head(TOP_N_TOPICS)
    # Extract top words for each topic
    topics_words = {topic: [word for word, _ in topic_model.get_topic(topic)] for topic in top_topics.Topic}

    # Step 5: Assign sample headlines to topics
    topic_assignments = defaultdict(list)
    for idx, topic in enumerate(topics):
        if topic in top_topics.Topic.values:
            if len(topic_assignments[topic]) < SAMPLE_HEADLINES_PER_TOPIC:
                topic_assignments[topic].append(processed_headlines[idx])

    # Step 6: Generate summaries for each topic
    summaries = {}
    for topic in top_topics.Topic:
        samples = topic_assignments.get(topic, [])
        if samples:
            summaries[topic] = samples[0]  # Using the first sample headline as the summary
        else:
            summaries[topic] = "No summary available."

    # Step 7: Export Trending Topics
    export_trending_topics(top_topics.itertuples(index=False), summaries, topic_assignments, topics_words,
                           output_dir=OUTPUT_DIR, filename_prefix='trending_topics')

    # Step 8: Export Topic Modeling Results
    export_topic_modeling_results(top_topics.itertuples(index=False), summaries, topic_assignments, topics_words,
                                  output_dir=OUTPUT_DIR, filename_prefix='topic_modeling')


# ----------------------------- Execute Script -----------------------------

if __name__ == "__main__":
    main()
