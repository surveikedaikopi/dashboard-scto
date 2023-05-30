FROM python:3.7-slim

# Set the time zone to Jakarta
ENV TZ=Asia/Jakarta
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Copy requirements file into container
COPY requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install -r /app/requirements.txt

# Copy application code
COPY . /app

# Set working directory
WORKDIR /app

# Expose port
EXPOSE 8501

# Copy entrypoint script
COPY entrypoint.sh /app/entrypoint.sh

# Set entrypoint script as executable
RUN chmod +x /app/entrypoint.sh

# Expose port for Streamlit
EXPOSE 8501

# Set entrypoint
ENTRYPOINT ["./entrypoint.sh"]
