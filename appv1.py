import numpy as np
import plost
import requests
import streamlit as st
import os
import random
from scapy.all import rdpcap
import collections
import tempfile
import sys
import pandas as pd
from scapy.utils import corrupt_bytes
from streamlit_echarts import st_echarts
import geoip2.database
import pydeck as pdk
import folium

# from scapy.layers.inet import IP,TCP,UDP,
from utils.pcap_decode import PcapDecode
import time

PD = PcapDecode()  # Parser
PCAPS = None  # Packets


def get_all_pcap(PCAPS, PD):
    pcaps = collections.OrderedDict()
    for count, i in enumerate(PCAPS, 1):
        pcaps[count] = PD.ether_decode(i)
    return pcaps


def get_filter_pcap(PCAPS, PD, key, value):
    pcaps = collections.OrderedDict()
    count = 1
    for p in PCAPS:
        pcap = PD.ether_decode(p)
        if key == 'Procotol':
            if value == pcap.get('Procotol').upper():
                pcaps[count] = pcap
                count += 1
            else:
                pass
        elif key == 'Source':
            if value == pcap.get('Source').upper():
                pcaps[count] = pcap
                count += 1
        elif key == 'Destination':
            if value == pcap.get('Destination').upper():
                pcaps[count] = pcap
                count += 1
        else:
            pass
    return pcaps


def process_json_data(json_data):
    # Convert JSON data to a pandas DataFrame
    df = pd.DataFrame.from_dict(json_data, orient='index')
    return df


# To Calculate Live Time
def calculate_live_time(pcap_data):
    timestamps = [float(packet.time) for packet in pcap_data]  # Convert to float
    start_time = min(timestamps)
    end_time = max(timestamps)
    live_time_duration = end_time - start_time
    live_time_duration_str = str(pd.Timedelta(seconds=live_time_duration))
    return start_time, end_time, live_time_duration, live_time_duration_str


# protocol length statistics
def pcap_len_statistic(PCAPS):
    pcap_len_dict = {'0-300': 0, '301-600': 0, '601-900': 0, '901-1200': 0, '1201-1500': 0, '1500-more': 0}
    for pcap in PCAPS:
        pcap_len = len(corrupt_bytes(pcap))
        if 0 < pcap_len < 300:
            pcap_len_dict['0-300'] += 1
        elif 301 <= pcap_len < 600:
            pcap_len_dict['301-600'] += 1
        elif 601 <= pcap_len < 900:
            pcap_len_dict['601-900'] += 1
        elif 901 <= pcap_len < 1200:
            pcap_len_dict['901-1200'] += 1
        elif 1201 <= pcap_len <= 1500:
            pcap_len_dict['1201-1500'] += 1
        elif pcap_len > 1500:
            pcap_len_dict['1500-more'] += 1
        else:
            pass
    return pcap_len_dict


# protocol freq statistics
def common_proto_statistic(PCAPS):
    common_proto_dict = collections.OrderedDict()
    common_proto_dict['IP'] = 0
    common_proto_dict['IPv6'] = 0
    common_proto_dict['TCP'] = 0
    common_proto_dict['UDP'] = 0
    common_proto_dict['ARP'] = 0
    common_proto_dict['ICMP'] = 0
    common_proto_dict['DNS'] = 0
    common_proto_dict['HTTP'] = 0
    common_proto_dict['HTTPS'] = 0
    common_proto_dict['Others'] = 0
    for pcap in PCAPS:
        if pcap.haslayer("IP"):
            common_proto_dict['IP'] += 1
        elif pcap.haslayer("IPv6"):
            common_proto_dict['IPv6'] += 1
        if pcap.haslayer("TCP"):
            common_proto_dict['TCP'] += 1
        elif pcap.haslayer("UDP"):
            common_proto_dict['UDP'] += 1
        if pcap.haslayer("ARP"):
            common_proto_dict['ARP'] += 1
        elif pcap.haslayer("ICMP"):
            common_proto_dict['ICMP'] += 1
        elif pcap.haslayer("DNS"):
            common_proto_dict['DNS'] += 1
        elif pcap.haslayer("TCP"):
            tcp = pcap.getlayer("TCP")
            dport = tcp.dport
            sport = tcp.sport
            if dport == 80 or sport == 80:
                common_proto_dict['HTTP'] += 1
            elif dport == 443 or sport == 443:
                common_proto_dict['HTTPS'] += 1
            else:
                common_proto_dict['Others'] += 1
        elif pcap.haslayer("UDP"):
            udp = pcap.getlayer("UDP")
            dport = udp.dport
            sport = udp.sport
            if dport == 5353 or sport == 5353:
                common_proto_dict['DNS'] += 1
            else:
                common_proto_dict['Others'] += 1
        elif pcap.haslayer("ICMPv6ND_NS"):
            common_proto_dict['ICMP'] += 1
        else:
            common_proto_dict['Others'] += 1
    return common_proto_dict


# maximum protocol statistics
def most_proto_statistic(PCAPS, PD):
    protos_list = list()
    for pcap in PCAPS:
        data = PD.ether_decode(pcap)
        protos_list.append(data['Procotol'])
    most_count_dict = collections.OrderedDict(collections.Counter(protos_list).most_common(10))
    return most_count_dict


# http/https Protocol Statistics
def http_statistic(PCAPS):
    http_dict = dict()
    for pcap in PCAPS:
        if pcap.haslayer("TCP"):
            tcp = pcap.getlayer("TCP")
            dport = tcp.dport
            sport = tcp.sport
            ip = None
            if dport == 80 or dport == 443:
                ip = pcap.getlayer("IP").dst
            elif sport == 80 or sport == 443:
                ip = pcap.getlayer("IP").src
            if ip:
                if ip in http_dict:
                    http_dict[ip] += 1
                else:
                    http_dict[ip] = 1
    return http_dict


def https_stats_main(PCAPS):
    http_dict = http_statistic(PCAPS)
    http_dict = sorted(http_dict.items(),
                       key=lambda d: d[1], reverse=False)
    http_key_list = list()
    http_value_list = list()
    for key, value in http_dict:
        http_key_list.append(key)
        http_value_list.append(value)
    return http_key_list, http_value_list


# DNS Protocol Statistics
def dns_statistic(PCAPS):
    dns_dict = dict()
    for pcap in PCAPS:
        if pcap.haslayer("DNSQR"):
            qname = pcap.getlayer("DNSQR").qname
            if qname in dns_dict:
                dns_dict[qname] += 1
            else:
                dns_dict[qname] = 1
    return dns_dict


def dns_stats_main(PCAPS):
    dns_dict = dns_statistic(PCAPS)
    dns_dict = sorted(dns_dict.items(), key=lambda d: d[1], reverse=False)
    dns_key_list = list()
    dns_value_list = list()
    for key, value in dns_dict:
        dns_key_list.append(key.decode('utf-8'))
        dns_value_list.append(value)
    return dns_key_list, dns_value_list


def time_flow(PCAPS):
    time_flow_dict = collections.OrderedDict()
    start = PCAPS[0].time
    time_flow_dict[time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(PCAPS[0].time)))] = len(
        corrupt_bytes(PCAPS[0]))
    for pcap in PCAPS:
        timediff = pcap.time - start
        time_flow_dict[float('%.3f' % timediff)] = len(corrupt_bytes(pcap))
    return time_flow_dict


def get_host_ip(PCAPS):
    ip_list = list()
    for pcap in PCAPS:
        if pcap.haslayer("IP"):
            ip_list.append(pcap.getlayer("IP").src)
            ip_list.append(pcap.getlayer("IP").dst)
    host_ip = collections.Counter(ip_list).most_common(1)[0][0]
    return host_ip


def data_flow(PCAPS, host_ip):
    data_flow_dict = {'IN': 0, 'OUT': 0}
    for pcap in PCAPS:
        if pcap.haslayer("IP"):
            if pcap.getlayer("IP").src == host_ip:
                data_flow_dict['OUT'] += 1
            elif pcap.getlayer("IP").dst == host_ip:
                data_flow_dict['IN'] += 1
            else:
                pass
    return data_flow_dict


def data_in_out_ip(PCAPS, host_ip):
    in_ip_packet_dict = dict()
    in_ip_len_dict = dict()
    out_ip_packet_dict = dict()
    out_ip_len_dict = dict()
    for pcap in PCAPS:
        if pcap.haslayer("IP"):
            dst = pcap.getlayer("IP").dst
            src = pcap.getlayer("IP").src
            pcap_len = len(corrupt_bytes(pcap))
            if dst == host_ip:
                if src in in_ip_packet_dict:
                    in_ip_packet_dict[src] += 1
                    in_ip_len_dict[src] += pcap_len
                else:
                    in_ip_packet_dict[src] = 1
                    in_ip_len_dict[src] = pcap_len
            elif src == host_ip:
                if dst in out_ip_packet_dict:
                    out_ip_packet_dict[dst] += 1
                    out_ip_len_dict[dst] += pcap_len
                else:
                    out_ip_packet_dict[dst] = 1
                    out_ip_len_dict[dst] = pcap_len
            else:
                pass

    in_packet_dict = in_ip_packet_dict
    in_len_dict = in_ip_len_dict
    out_packet_dict = out_ip_packet_dict
    out_len_dict = out_ip_len_dict
    in_packet_dict = sorted(in_packet_dict.items(), key=lambda d: d[1], reverse=False)
    in_len_dict = sorted(in_len_dict.items(), key=lambda d: d[1], reverse=False)
    out_packet_dict = sorted(out_packet_dict.items(), key=lambda d: d[1], reverse=False)
    out_len_dict = sorted(out_len_dict.items(), key=lambda d: d[1], reverse=False)
    in_keyp_list = list()
    in_packet_list = list()
    for key, value in in_packet_dict:
        in_keyp_list.append(key)
        in_packet_list.append(value)
    in_keyl_list = list()
    in_len_list = list()
    for key, value in in_len_dict:
        in_keyl_list.append(key)
        in_len_list.append(value)
    out_keyp_list = list()
    out_packet_list = list()
    for key, value in out_packet_dict:
        out_keyp_list.append(key)
        out_packet_list.append(value)
    out_keyl_list = list()
    out_len_list = list()
    for key, value in out_len_dict:
        out_keyl_list.append(key)
        out_len_list.append(value)
    in_ip_dict = {'in_keyp': in_keyp_list, 'in_packet': in_packet_list, 'in_keyl': in_keyl_list, 'in_len': in_len_list,
                  'out_keyp': out_keyp_list, 'out_packet': out_packet_list, 'out_keyl': out_keyl_list,
                  'out_len': out_len_list}
    return in_ip_dict


def proto_flow(PCAPS):
    proto_flow_dict = collections.OrderedDict()
    proto_flow_dict['IP'] = 0
    proto_flow_dict['IPv6'] = 0
    proto_flow_dict['TCP'] = 0
    proto_flow_dict['UDP'] = 0
    proto_flow_dict['ARP'] = 0
    proto_flow_dict['ICMP'] = 0
    proto_flow_dict['DNS'] = 0
    proto_flow_dict['HTTP'] = 0
    proto_flow_dict['HTTPS'] = 0
    proto_flow_dict['Others'] = 0
    for pcap in PCAPS:
        pcap_len = len(corrupt_bytes(pcap))
        if pcap.haslayer("IP"):
            proto_flow_dict['IP'] += pcap_len
        elif pcap.haslayer("IPv6"):
            proto_flow_dict['IPv6'] += pcap_len
        if pcap.haslayer("TCP"):
            proto_flow_dict['TCP'] += pcap_len
        elif pcap.haslayer("UDP"):
            proto_flow_dict['UDP'] += pcap_len
        if pcap.haslayer("ARP"):
            proto_flow_dict['ARP'] += pcap_len
        elif pcap.haslayer("ICMP"):
            proto_flow_dict['ICMP'] += pcap_len
        elif pcap.haslayer("DNS"):
            proto_flow_dict['DNS'] += pcap_len
        elif pcap.haslayer("TCP"):
            tcp = pcap.getlayer("TCP")
            dport = tcp.dport
            sport = tcp.sport
            if dport == 80 or sport == 80:
                proto_flow_dict['HTTP'] += pcap_len
            elif dport == 443 or sport == 443:
                proto_flow_dict['HTTPS'] += pcap_len
            else:
                proto_flow_dict['Others'] += pcap_len
        elif pcap.haslayer("UDP"):
            udp = pcap.getlayer("UDP")
            dport = udp.dport
            sport = udp.sport
            if dport == 5353 or sport == 5353:
                proto_flow_dict['DNS'] += pcap_len
            else:
                proto_flow_dict['Others'] += pcap_len
        elif pcap.haslayer("ICMPv6ND_NS"):
            proto_flow_dict['ICMP'] += pcap_len
        else:
            proto_flow_dict['Others'] += pcap_len
    return proto_flow_dict


def most_flow_statistic(PCAPS, PD):
    most_flow_dict = collections.defaultdict(int)
    for pcap in PCAPS:
        data = PD.ether_decode(pcap)
        most_flow_dict[data['Procotol']] += len(corrupt_bytes(pcap))
    return most_flow_dict


def getmyip():
    try:
        headers = {'User-Agent': 'Baiduspider+(+http://www.baidu.com/search/spider.htm'}
        ip = requests.get('http://icanhazip.com', headers=headers).text
        return ip.strip()
    except:
        return None


def get_geo(ip):
    reader = geoip2.database.Reader('utils/GeoIP/GeoLite2-City.mmdb')
    try:
        response = reader.city(ip)
        # city_name = response.country.names['zh-CN']+response.city.names['zh-CN']
        city_name = response.country.names['en'] + response.city.names['en']
        longitude = response.location.longitude
        latitude = response.location.latitude
        return [city_name, longitude, latitude]
    except:
        return None


def get_ipmap(PCAPS, host_ip):
    geo_dict = dict()
    ip_value_dict = dict()
    ip_value_list = list()
    for pcap in PCAPS:
        if pcap.haslayer("IP"):
            src = pcap.getlayer("IP").src
            dst = pcap.getlayer("IP").dst
            pcap_len = len(corrupt_bytes(pcap))
            if src == host_ip:
                oip = dst
            else:
                oip = src
            if oip in ip_value_dict:
                ip_value_dict[oip] += pcap_len
            else:
                ip_value_dict[oip] = pcap_len
    for ip, value in ip_value_dict.items():
        geo_list = get_geo(ip)
        if geo_list:
            geo_dict[geo_list[0]] = [geo_list[1], geo_list[2]]
            Mvalue = str(float('%.2f' % (value / 1024.0))) + ':' + ip
            ip_value_list.append({geo_list[0]: Mvalue})
        else:
            pass
    return [geo_dict, ip_value_list]


# def ipmap(PCAPS):
#     myip = getmyip()
#     host_ip = get_host_ip(PCAPS)
#     ipdata = get_ipmap(PCAPS, host_ip)
#     geo_dict = ipdata[0]
#     ip_value_list = ipdata[1]
#     myip_geo = get_geo(myip)
#     ip_value_list = [(list(d.keys())[0], list(d.values())[0])
#                      for d in ip_value_list]
#     # print('ip_value_list', ip_value_list)
#     # print('geo_dict', geo_dict)
#     # return render_template('./dataanalyzer/ipmap.html', geo_data=geo_dict, ip_value=ip_value_list, mygeo=myip_geo)
#     return geo_dict, ip_value_list, myip_geo


def ipmap(PCAPS):
    # Assuming these functions are defined elsewhere in your code
    myip = getmyip()
    host_ip = get_host_ip(PCAPS)
    ipdata = get_ipmap(PCAPS, host_ip)
    geo_dict = ipdata[0]
    ip_value_list = ipdata[1]
    myip_geo = get_geo(myip)
    ip_value_list = [(list(d.keys())[0], list(d.values())[0]) for d in ip_value_list]

    # Create DataFrames from the dictionaries and lists
    geo_df = pd.DataFrame(list(geo_dict.items()), columns=['Location', 'Coordinates'])
    ip_df = pd.DataFrame(ip_value_list, columns=['Location', 'IP'])

    # Check if myip_geo is not None before creating the DataFrame
    if myip_geo is not None:
        myip_geo_df = pd.DataFrame(list(myip_geo.items()), columns=['MyLocation', 'MyCoordinates'])

        # Merge the DataFrames based on the 'Location' column
        merged_df = geo_df.merge(ip_df, on='Location', how='left').merge(myip_geo_df, left_on='Location',
                                                                         right_on='MyLocation', how='left')
    else:
        # If myip_geo is None, merge only geo_df and ip_df
        merged_df = geo_df.merge(ip_df, on='Location', how='left')

    # Split the 'IP' column into 'Numeric_Value' and 'IP_Address'
    merged_df[['Data_Traffic', 'IP_Address']] = merged_df['IP'].str.split(':', expand=True)

    # Drop the original 'IP' column
    merged_df = merged_df.drop('IP', axis=1)

    # Display the merged DataFrame
    st.write(merged_df)

    return merged_df


def main():
    st.set_page_config(page_title="PCAP Dashboard", page_icon="📈", layout="wide")
    st.title("File Upload App")

    # File uploader widget
    uploaded_file = st.file_uploader("Choose a file", type=["csv", "txt", "xlsx", "pcap", "cap"])

    if uploaded_file is not None:
        # Display file details
        file_details = {"FileName": uploaded_file.name, "FileType": uploaded_file.type, "FileSize": uploaded_file.size}
        st.write("File Details:", file_details)

        # Check if the uploaded file is a PCAP file
        if uploaded_file.type == "application/octet-stream":
            # Process the uploaded PCAP file
            pcap_data = rdpcap(os.path.join(uploaded_file.name))

            # Example: Get all PCAPs
            all_data = get_all_pcap(pcap_data, PD)
            dataframe_data = process_json_data(all_data)
            start_time, end_time, live_time_duration, live_time_duration_str = calculate_live_time(pcap_data)
            # Add live time information to the data frame
            # dataframe_data['Start Time'] = start_time
            # dataframe_data['End Time'] = end_time
            dataframe_data['Live Time Duration'] = live_time_duration_str
            st.sidebar.header("P1ease Filter Here:")
            procotol = st.sidebar.multiselect(
                "Select Protocol:",
                options=dataframe_data["Procotol"].unique(),default=None)

            if procotol is None or not procotol:
                st.write("All PCAPs:")
                Data_to_display_df1 = dataframe_data.copy()
                st.dataframe(Data_to_display_df1, use_container_width=True)

            else:
                Data_to_display_df1 = dataframe_data[dataframe_data["Procotol"].isin(procotol)]
                st.write("Filtered PCAPs:")
                st.dataframe(Data_to_display_df1)

            # Sidebar slider for filtering
            filter_value_len = st.sidebar.slider("Filter by Numeric Column", min_value=min(dataframe_data["len"]),
                                             max_value=max(dataframe_data["len"]),
                                             value=(min(dataframe_data["len"]), max(dataframe_data["len"])))

            if not filter_value_len:
               Data_to_display_df2=Data_to_display_df1.copy()
               st.dataframe(Data_to_display_df2, use_container_width=True)

            else:
               Data_to_display_df2 = Data_to_display_df1[(Data_to_display_df1["len"] >= filter_value_len[0]) & (Data_to_display_df1["len"] <= filter_value_len[1])]
               st.dataframe(Data_to_display_df2, use_container_width=True)

        else:
            st.warning("Please upload a valid PCAP file.")


if __name__ == "__main__":
    main()
